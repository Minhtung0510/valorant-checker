from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import socket
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


KEY_PREFIX = "VC1"
PRODUCT_ID = "valorant-checker-desktop"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def normalize_machine_id(value: str) -> str:
    compact = "".join(ch for ch in value.upper() if ch.isalnum())
    return "-".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def get_machine_id() -> str:
    parts = [platform.system(), platform.machine(), socket.gethostname()]

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                parts.append(str(winreg.QueryValueEx(key, "MachineGuid")[0]))
        except OSError:
            parts.append(str(uuid.getnode()))
    else:
        machine_id_file = Path("/etc/machine-id")
        if machine_id_file.exists():
            parts.append(machine_id_file.read_text(encoding="utf-8").strip())
        else:
            parts.append(str(uuid.getnode()))

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return normalize_machine_id(digest)


@dataclass(frozen=True)
class LicenseClaims:
    version: int
    product: str
    key_id: str
    customer: str
    issued_at: int
    expires_at: int
    machine_id: str = ""
    note: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LicenseClaims":
        return cls(
            version=int(value["version"]),
            product=str(value["product"]),
            key_id=str(value["key_id"]),
            customer=str(value.get("customer", "")),
            issued_at=int(value["issued_at"]),
            expires_at=int(value["expires_at"]),
            machine_id=normalize_machine_id(str(value.get("machine_id", ""))),
            note=str(value.get("note", "")),
        )


@dataclass(frozen=True)
class LicenseValidation:
    valid: bool
    message: str
    claims: Optional[LicenseClaims] = None


def generate_keypair(private_path: Path, public_path: Path, force: bool = False) -> None:
    private_path = Path(private_path)
    public_path = Path(public_path)
    if not force and (private_path.exists() or public_path.exists()):
        raise FileExistsError("License keypair already exists. Use force=True to replace it.")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def create_license_key(
    private_key_path: Path,
    customer: str,
    expires_at: int,
    machine_id: str = "",
    note: str = "",
    issued_at: Optional[int] = None,
) -> tuple[str, LicenseClaims]:
    private_key = serialization.load_pem_private_key(
        Path(private_key_path).read_bytes(),
        password=None,
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("Private key is not an Ed25519 key")

    claims = LicenseClaims(
        version=1,
        product=PRODUCT_ID,
        key_id=uuid.uuid4().hex[:16].upper(),
        customer=customer.strip(),
        issued_at=int(issued_at or time.time()),
        expires_at=int(expires_at),
        machine_id=normalize_machine_id(machine_id),
        note=note.strip(),
    )
    payload = json.dumps(
        asdict(claims),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = private_key.sign(payload)
    return f"{KEY_PREFIX}.{_b64encode(payload)}.{_b64encode(signature)}", claims


def verify_license_key(
    license_key: str,
    public_key_path: Path,
    machine_id: Optional[str] = None,
    now: Optional[int] = None,
) -> LicenseValidation:
    try:
        prefix, payload_text, signature_text = license_key.strip().split(".", 2)
        if prefix != KEY_PREFIX:
            return LicenseValidation(False, "Sai định dạng key")

        payload = _b64decode(payload_text)
        signature = _b64decode(signature_text)
        public_key = serialization.load_pem_public_key(Path(public_key_path).read_bytes())
        if not isinstance(public_key, Ed25519PublicKey):
            return LicenseValidation(False, "Public key không hợp lệ")
        public_key.verify(signature, payload)

        claims = LicenseClaims.from_dict(json.loads(payload.decode("utf-8")))
        if claims.version != 1 or claims.product != PRODUCT_ID:
            return LicenseValidation(False, "Key không dành cho ứng dụng này")

        current_time = int(now or time.time())
        if claims.issued_at > current_time + 300:
            return LicenseValidation(False, "Thời gian hệ thống không hợp lệ")
        if current_time >= claims.expires_at:
            return LicenseValidation(False, "Key đã hết hạn", claims)

        current_machine = normalize_machine_id(machine_id or get_machine_id())
        if claims.machine_id and claims.machine_id != current_machine:
            return LicenseValidation(False, "Key không thuộc máy này", claims)

        return LicenseValidation(True, "Key hợp lệ", claims)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return LicenseValidation(False, "Key bị lỗi hoặc sai định dạng")
    except InvalidSignature:
        return LicenseValidation(False, "Chữ ký key không hợp lệ")
    except OSError as exc:
        return LicenseValidation(False, f"Không đọc được public key: {exc}")

