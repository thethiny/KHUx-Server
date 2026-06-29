"""
Generate self-signed CA + server certificates for KHUx private server.

Creates:
  ca.pem / ca.key          - Custom CA (install this on BlueStacks)
  cert.pem / key.pem       - Server cert signed by CA (for both game domains)
  ca_android.0             - CA cert in Android system format (for /system/etc/security/cacerts/)

Usage:
  python setup_certs.py
"""

import hashlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
except ImportError:
    print("Missing cryptography library. Install with: pip install cryptography")
    sys.exit(1)


DOMAINS = [
    "api-s.kingdomhearts.com",
    "psg.sqex-bridge.jp",
    "cache.sqex-bridge.jp",
    "localhost",
]

OUT_DIR = Path(__file__).parent


def generate_ca():
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "KHUx Private Server CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KHUx"),
    ])

    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    return ca_key, ca_cert


def generate_server_cert(ca_key, ca_cert):
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    san_names = [x509.DNSName(d) for d in DOMAINS]
    san_names.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))

    server_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, DOMAINS[0]),
        ]))
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san_names),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    return server_key, server_cert


def make_android_cert_name(ca_cert):
    """Android names system CA certs by the subject hash in OpenSSL format."""
    subject_der = ca_cert.subject.public_bytes()
    h = hashlib.md5(subject_der).hexdigest()
    # Android uses the first 8 hex chars of the subject_hash_old
    # We'll just use the hash and let the user rename if needed
    return h[:8] + ".0"


def main():
    import ipaddress  # noqa: delayed import to keep it clean

    # Make ipaddress available in generate_server_cert scope
    global ipaddress
    import ipaddress

    print("Generating CA key pair...")
    ca_key, ca_cert = generate_ca()

    print("Generating server certificate...")
    server_key, server_cert = generate_server_cert(ca_key, ca_cert)

    # Write CA
    ca_key_path = OUT_DIR / "ca.key"
    ca_cert_path = OUT_DIR / "ca.pem"

    ca_key_path.write_bytes(ca_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    # Write server cert
    key_path = OUT_DIR / "key.pem"
    cert_path = OUT_DIR / "cert.pem"

    key_path.write_bytes(server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))

    # Write Android-format CA cert (DER)
    android_name = make_android_cert_name(ca_cert)
    android_path = OUT_DIR / android_name
    # Android wants PEM format with the hash name
    android_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    print()
    print(f"  CA certificate:     {ca_cert_path}")
    print(f"  CA key:             {ca_key_path}")
    print(f"  Server certificate: {cert_path}")
    print(f"  Server key:         {key_path}")
    print(f"  Android CA cert:    {android_path}")
    print()
    print(f"  Domains covered: {', '.join(DOMAINS)}")
    print()
    print("Next steps:")
    print("  1. Push CA to BlueStacks:  adb push", android_name, "/system/etc/security/cacerts/")
    print("  2. Set permissions:        adb shell chmod 644 /system/etc/security/cacerts/" + android_name)
    print("  3. Edit hosts file:        See SETUP.md")
    print("  4. Start server:           python run.py --ssl")


if __name__ == "__main__":
    main()
