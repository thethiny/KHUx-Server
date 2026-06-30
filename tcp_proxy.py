import socket
import threading
import sys

LISTEN_PORT = 80
FORWARD_HOST = "127.0.0.1"
FORWARD_PORT = 8888

def relay(src, dst, label):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            text = data.decode("latin-1")
            lines = text.split("\r\n")
            for line in lines[:5]:
                if line.strip():
                    print(f"[{label}] {line[:200]}", flush=True)
            if label == "RESP" and ("HTTP" in lines[0]):
                body_start = text.find("\r\n\r\n")
                if body_start >= 0:
                    body = text[body_start+4:]
                    print(f"[{label} BODY] {body[:500]}", flush=True)
            dst.sendall(data)
    except Exception as e:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle(client):
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream.connect((FORWARD_HOST, FORWARD_PORT))
    t1 = threading.Thread(target=relay, args=(client, upstream, "REQ"), daemon=True)
    t2 = threading.Thread(target=relay, args=(upstream, client, "RESP"), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", LISTEN_PORT))
    srv.listen(10)
    print(f"TCP proxy listening on :{LISTEN_PORT} -> {FORWARD_HOST}:{FORWARD_PORT}", flush=True)
    while True:
        client, addr = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()

if __name__ == "__main__":
    main()
