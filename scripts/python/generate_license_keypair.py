from __future__ import annotations

import argparse
from pathlib import Path

from license_core import generate_keypair


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Ed25519 license keypair")
    parser.add_argument("--force", action="store_true", help="Replace an existing keypair")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    private_path = base / "license_private_key.pem"
    public_path = base / "license_public_key.pem"
    generate_keypair(private_path, public_path, force=args.force)
    print(f"Private key: {private_path}")
    print(f"Public key:  {public_path}")
    print("Keep the private key offline. Only the public key is bundled into the client app.")


if __name__ == "__main__":
    main()
