import socket
import struct
import threading

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 15353
UPSTREAM_DNS = "8.8.8.8"
REDIRECT_IP = "192.168.1.119"
REDIRECT_DOMAIN = "api.sp.kingdomhearts.com"

def build_response(query, redirect_ip):
    response = bytearray(query)
    response[2] = 0x81  # QR=1, RD=1
    response[3] = 0x80  # RA=1
    response[6:8] = struct.pack("!H", 1)  # ANCOUNT=1
    # Append answer: pointer to name in question, type A, class IN, TTL 300, RDLENGTH 4, IP
    answer = struct.pack("!HHIH", 0xC00C, 1, 1, 300)
    answer += struct.pack("!H", 4)
    answer += socket.inet_aton(redirect_ip)
    return bytes(response) + answer

def extract_domain(data):
    domain_parts = []
    idx = 12  # skip header
    while idx < len(data):
        length = data[idx]
        if length == 0:
            break
        idx += 1
        domain_parts.append(data[idx:idx+length].decode(errors='replace'))
        idx += length
    return ".".join(domain_parts)

def handle_query(sock, data, addr):
    domain = extract_domain(data)
    if domain.lower() == REDIRECT_DOMAIN:
        print(f"[DNS] {domain} -> {REDIRECT_IP} (redirected)")
        response = build_response(data, REDIRECT_IP)
        sock.sendto(response, addr)
    else:
        # Forward to upstream
        upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        upstream.settimeout(5)
        try:
            upstream.sendto(data, (UPSTREAM_DNS, 53))
            response, _ = upstream.recvfrom(4096)
            sock.sendto(response, addr)
        except Exception as e:
            print(f"[DNS] {domain} -> upstream error: {e}")
        finally:
            upstream.close()

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    print(f"[DNS] Listening on {LISTEN_IP}:{LISTEN_PORT}, redirecting {REDIRECT_DOMAIN} -> {REDIRECT_IP}")
    while True:
        data, addr = sock.recvfrom(4096)
        threading.Thread(target=handle_query, args=(sock, data, addr), daemon=True).start()

if __name__ == "__main__":
    main()
