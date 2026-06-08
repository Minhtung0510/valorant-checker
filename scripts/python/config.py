"""
config.py — Constants, headers, UUIDs, env defaults
"""
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDS_PATH", "credentials.json")

# .env defaults
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
DELAY_MIN = float(os.getenv("DELAY_MIN", "0.3"))   # was 3s
DELAY_MAX = float(os.getenv("DELAY_MAX", "1.2"))   # was 6s

# Riot headers platform
RIOT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVm"
    "Vyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
)

# Item / currency type UUIDs
UUID_VP = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
UUID_RP = "e59aa87c-4cbf-517a-5983-6e81511be9b7"
UUID_KC = "85ca954a-41f2-4a9f-9e6b-0283ccc65d64"
UUID_FA = "f2c6e9b4-8d7a-4c3e-9f1b-5a7d3e9f2c6b"
UUID_SKINS = "2e8df286-8182-4808-b975-0406276e02c8"

# Riot Auth URL — token flow (current, 1h token)
RIOT_AUTH_URL = (
    "https://auth.riotgames.com/authorize"
    "?redirect_uri=http://localhost/redirect"
    "&client_id=riot-client"
    "&response_type=token%20id_token"
    "&nonce=1"
    "&scope=openid%20link%20ban%20lol_region%20account"
)

# Riot Auth URL — code flow (refresh_token support, token ton tai hang tuan)
RIOT_AUTH_CODE_URL = (
    "https://auth.riotgames.com/authorize"
    "?redirect_uri=http://localhost/redirect"
    "&client_id=riot-client"
    "&response_type=code"
    "&nonce=1"
    "&scope=openid%20link%20ban%20lol_region%20account"
)

# Token exchange endpoint
RIOT_TOKEN_URL = "https://auth.riotgames.com/api/v1/authorization"

# Riot logout URL
RIOT_LOGOUT_URL = "https://auth.riotgames.com/logout"

# Rank names (tier 0-25)
RANK_NAMES = [
    "Unrated", "Iron 1", "Iron 2", "Iron 3",
    "Bronze 1", "Bronze 2", "Bronze 3",
    "Silver 1", "Silver 2", "Silver 3",
    "Gold 1", "Gold 2", "Gold 3",
    "Platinum 1", "Platinum 2", "Platinum 3",
    "Diamond 1", "Diamond 2", "Diamond 3",
    "Ascendant 1", "Ascendant 2", "Ascendant 3",
    "Immortal 1", "Immortal 2", "Immortal 3",
    "Radiant",
]

# httpx retry config
HTTPX_TIMEOUT = 10.0
HTTPX_MAX_RETRIES = 3
