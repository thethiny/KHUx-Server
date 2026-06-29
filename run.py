"""
Quick-start script for the KHUx private server.

Usage:
    python run.py              # HTTP on port 80 (v1.0.1 client uses plain HTTP)
    python run.py --ssl        # HTTPS on port 443 (later client versions)
    python run.py --port 8080  # Custom port
    python run.py --fresh      # Delete DB and cache before starting

DNS redirect needed:
    api.sp.kingdomhearts.com -> your IP  (v1.0.1)
    api-s.kingdomhearts.com  -> your IP  (v5.0.1)
    psg.sqex-bridge.jp       -> your IP  (bridge/auth)
"""

import argparse
import glob
import os
import uvicorn

TEMP_PATTERNS = ["*.db", "*.sqlite", "*.log", "__pycache__"]


def fresh_clean():
    here = os.path.dirname(os.path.abspath(__file__))
    for pattern in ["*.db", "*.sqlite"]:
        for f in glob.glob(os.path.join(here, pattern)):
            os.remove(f)
            print(f"  Deleted {os.path.basename(f)}")
    cache_dir = os.path.join(here, ".cache")
    if os.path.isdir(cache_dir):
        import shutil
        shutil.rmtree(cache_dir)
        print("  Deleted .cache/")
    log_file = os.path.join(os.path.dirname(here), "server.log")
    if os.path.exists(log_file):
        os.remove(log_file)
        print("  Deleted server.log")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KHUx Private Server")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with key.pem/cert.pem")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--fresh", action="store_true", help="Delete DB, cache, and logs before starting")
    args = parser.parse_args()

    if args.fresh:
        print("Cleaning temp files...")
        fresh_clean()
        print()

    kwargs = {
        "app": "src.app:app",
        "host": args.host,
        "port": args.port or (443 if args.ssl else 80),
        "log_level": "info",
    }

    if args.ssl:
        kwargs["ssl_keyfile"] = "key.pem"
        kwargs["ssl_certfile"] = "cert.pem"

    uvicorn.run(**kwargs)
