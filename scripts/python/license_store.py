from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app_runtime import app_data_dir, resource_path
from license_core import LicenseClaims, LicenseValidation, get_machine_id, verify_license_key


PUBLIC_KEY_PATH = resource_path("license_public_key.pem")
STATE_PATH = app_data_dir() / "license_state.json"


@dataclass(frozen=True)
class StoredLicense:
    key: str
    claims: LicenseClaims

    @property
    def expiry_text(self) -> str:
        return datetime.fromtimestamp(self.claims.expires_at).strftime("%d/%m/%Y %H:%M")


def _read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(value: dict) -> None:
    temp_path = STATE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp_path.replace(STATE_PATH)


def activate_license(license_key: str) -> LicenseValidation:
    now = int(time.time())
    validation = verify_license_key(
        license_key,
        PUBLIC_KEY_PATH,
        machine_id=get_machine_id(),
        now=now,
    )
    if validation.valid and validation.claims:
        _write_state(
            {
                "license_key": license_key.strip(),
                "activated_at": now,
                "last_seen": now,
            }
        )
    return validation


def load_valid_license() -> tuple[Optional[StoredLicense], str]:
    state = _read_state()
    license_key = str(state.get("license_key", "")).strip()
    if not license_key:
        return None, "Chưa kích hoạt license"

    now = int(time.time())
    last_seen = int(state.get("last_seen", 0) or 0)
    if last_seen and now + 300 < last_seen:
        return None, "Phát hiện thời gian hệ thống bị lùi"

    validation = verify_license_key(
        license_key,
        PUBLIC_KEY_PATH,
        machine_id=get_machine_id(),
        now=now,
    )
    if not validation.valid or not validation.claims:
        return None, validation.message

    state["last_seen"] = max(last_seen, now)
    _write_state(state)
    return StoredLicense(license_key, validation.claims), validation.message


def clear_license() -> None:
    try:
        STATE_PATH.unlink()
    except FileNotFoundError:
        pass

