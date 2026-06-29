"""
KHUx private server encryption layer.

The game client uses AES-256-CBC with a zero IV for all API communication.

v1.0.1 request:  v=<urlencode(base64(AES-CBC-encrypt(json)))>
v5.0.1 request:  v=<urlencode(base64(AES-CBC-encrypt(json)))>&m=<mode>&i=<session_index>
Both responses:  urlencode(base64(AES-CBC-encrypt(json)))
"""

import json
import os
from base64 import b64decode, b64encode
from urllib.parse import parse_qs, quote, unquote

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

ZERO_IV = b"\x00" * 16
AES_BLOCK_BITS = 128


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-256-CBC encrypt with zero IV and PKCS7 padding."""
    padder = PKCS7(AES_BLOCK_BITS).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(ZERO_IV))
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """AES-256-CBC decrypt with zero IV, strip PKCS7 padding."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(ZERO_IV))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(AES_BLOCK_BITS).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def decrypt_request(body: str, key: bytes) -> dict:
    """
    Decrypt an encrypted game API request.

    Both v1.0.1 and v5.0.1 use v=<encrypted> as the first param.
    v5.0.1 also has &m=<mode>&i=<index> which we ignore.
    """
    params = parse_qs(body)
    v_encoded = params["v"][0]
    v_decoded = unquote(v_encoded)
    ciphertext = b64decode(v_decoded)
    plaintext = decrypt(ciphertext, key)
    return json.loads(plaintext)


def encrypt_response(data: dict, key: bytes) -> str:
    """
    Encrypt a game API response.

    JSON serialize → AES encrypt → base64 encode → URL-encode.
    """
    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    ciphertext = encrypt(plaintext, key)
    b64 = b64encode(ciphertext).decode("ascii")
    return quote(b64)
