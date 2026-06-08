"""
sheets.py — File-based accounts (accounts.txt) + output folder (Check-done)
"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from config import PROJECT_ROOT

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", r"C:\Users\WORK\Desktop\Check-done"))
ACCOUNTS_FILE = PROJECT_ROOT / "accounts.txt"

# ── rank helpers ─────────────────────────────────────────────────────────

RANK_NAMES = [
    "Unrated","Iron 1","Iron 2","Iron 3",
    "Bronze 1","Bronze 2","Bronze 3",
    "Silver 1","Silver 2","Silver 3",
    "Gold 1","Gold 2","Gold 3",
    "Platinum 1","Platinum 2","Platinum 3",
    "Diamond 1","Diamond 2","Diamond 3",
    "Ascendant 1","Ascendant 2","Ascendant 3",
    "Immortal 1","Immortal 2","Immortal 3",
    "Radiant",
]

def rank_str(tier: int, rr: int) -> str:
    if tier <= 0:
        return "Unrated"
    name = RANK_NAMES[tier] if tier < len(RANK_NAMES) else f"Rank {tier}"
    return f"{name} — {rr} RR"

def safe_file(s: str) -> str:
    return re.sub(r'[#:/\\?*"|<>]', "_", str(s))[:80]

def esc(s):
    if not s and s != 0:
        return ""
    return (str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;"))

def cat_of(n: int) -> str:
    if n <= 0:    return "0_skin"
    if n <= 20:   return "1-20_skins"
    if n <= 40:   return "20-40_skins"
    if n <= 60:   return "40-60_skins"
    if n <= 100:  return "60-100_skins"
    return "100plus_skins"

CAT_COLORS  = {
    "0_skin": "#9e9e9e",
    "1-20_skins": "#f5a623",
    "20-40_skins": "#2196f3",
    "40-60_skins": "#9c27b0",
    "60-100_skins": "#4caf50",
    "100plus_skins": "#ff4655",
    "error": "#ff5252"
}
CAT_LABELS  = {
    "0_skin": "0 Skin",
    "1-20_skins": "1-20 Skins",
    "20-40_skins": "20-40 Skins",
    "40-60_skins": "40-60 Skins",
    "60-100_skins": "60-100 Skins",
    "100plus_skins": "100+ Skins",
    "error": "Error"
}

# ── accounts file ───────────────────────────────────────────────────────

def get_accounts() -> list[dict]:
    if not ACCOUNTS_FILE.exists():
        raise FileNotFoundError(
            f"Khong tim thay {ACCOUNTS_FILE}\n"
            "Tao file voi dinh dang:\n"
            "  username@gmail.com:password[:ap]\n"
            "  username2@riot.com:password2[:na]"
        )

    accounts = []
    for line in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        parts = line.split(":", 2)
        username = parts[0].strip()
        password = parts[1].strip()
        region   = parts[2].strip() if len(parts) > 2 else "ap"
        if username and password:
            accounts.append({"username": username, "password": password, "region": region})
    return accounts

# ── HTML ────────────────────────────────────────────────────────────────

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
header{background:#1a2634;border-bottom:2px solid #ff4655;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.logo{width:36px;height:36px}
header .brand{display:flex;align-items:center;gap:12px}
header .brand .name{font-size:1.2em;font-weight:700;color:#ff4655;letter-spacing:1px}
.badge{display:inline-block;padding:3px 12px;border-radius:12px;font-size:.8em;font-weight:700;border:1px solid COLOR_PLACEHOLDER;color:COLOR_PLACEHOLDER}
.badge.banned{border-color:#ff5252;color:#ff5252}
main{max-width:1100px;margin:0 auto;padding:20px 24px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.card{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:16px}
.card h3{color:#ff4655;font-size:.72em;text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #2a3a4a}
.row{display:flex;padding:7px 0;border-bottom:1px solid rgba(42,58,74,.3);font-size:.88em;gap:10px}
.row:last-child{border-bottom:none}
.row .l{color:#8b978f;min-width:130px;flex-shrink:0}
.row .v{font-weight:600;color:#ece8e1;word-break:break-all}
.row .v.sm{font-size:.75em}
.ok,.bad{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8em;font-weight:600}
.ok{background:#1b5e20;color:#4caf50}
.bad{background:#2a1a1a;color:#ff5252}
.wg{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:12px}
.wc{background:#0d1520;border:1px solid #2a3a4a;border-radius:8px;padding:10px;text-align:center}
.wc .v{font-size:1.1em;font-weight:700;color:#ff4655}
.wc .l{font-size:.68em;color:#8b978f;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.sec{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:16px;margin-bottom:16px}
.sec h3{color:#8b978f;font-size:.72em;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.t{width:100%;border-collapse:separate;border-spacing:0}
.t th{text-align:left;color:#8b978f;font-size:.72em;text-transform:uppercase;letter-spacing:.5px;padding:6px 10px}
.t td{background:#0d1520;padding:7px 10px;font-size:.85em;border-bottom:4px solid #1a2634}
.t td:first-child{color:#ff4655;font-weight:700;width:40px;text-align:center;border-radius:6px 0 0 6px}
.t td:last-child{border-radius:0 6px 6px 0}
.t tr:hover td{background:#162030}
footer{text-align:center;color:#8b978f;font-size:.78em;padding:20px;border-top:1px solid #2a3a4a;margin-top:20px}
@media(max-width:700px){.two-col{grid-template-columns:1fr}.wg{grid-template-columns:1fr 1fr}}
"""


def account_html(d: dict, cat: str) -> str:
    color = CAT_COLORS.get(cat, "#8b978f")
    label = CAT_LABELS.get(cat, cat)
    tier  = d.get("current_tier", 0)
    rr    = d.get("current_rr", 0)
    rank  = rank_str(tier, rr)
    banned = d.get("is_banned", False)

    # badge
    if banned:
        badge = '<span class="badge banned">' + esc(d.get("account_status", "BANNED")) + '</span>'
    else:
        badge = '<span class="badge" style="COLOR">' + label + '</span>'
    badge = badge.replace("COLOR", f'border-color:{color};color:{color}')

    # banner
    banner = ""
    if banned:
        banner = '<div style="background:rgba(183,28,28,.2);border:1px solid #b71c1c;border-radius:8px;padding:14px;margin-bottom:16px;color:#ff5252;font-weight:600">&#9888; ' + esc(d.get("account_status", "BANNED")) + '</div>'

    # wallet
    vp = (d.get("vp") or 0)
    rp = (d.get("rp") or 0)
    kc = (d.get("kc") or 0)
    fa = (d.get("fa") or 0)

    # purchases
    tx_rows = ""
    for i, tx in enumerate(d.get("purchases", [])[:20], 1):
        tx_rows += f"<tr><td>{i}</td><td>{esc(tx.get('amount',''))} {esc(tx.get('currency',''))}</td><td>{esc(tx.get('method',''))}</td><td>{esc(tx.get('date',''))}</td></tr>"
    tx_section = ""
    if tx_rows:
        tx_section = f'<div class="sec"><h3>Purchase History</h3><table class="t"><thead><tr><th>#</th><th>Amount</th><th>Method</th><th>Date</th></tr></thead><tbody>{tx_rows}</tbody></table></div>'

    # status badge
    status = d.get("account_status", "Active")
    if status == "Active":
        status_html = '<span class="ok">Active</span>'
    else:
        status_html = '<span class="bad">' + esc(status) + '</span>'

    # email/phone verified
    email_v = "Yes" if d.get("email_verified") else "No"
    phone_v = "Yes" if d.get("phone_verified") else "No"

    # inject CSS color
    css = CSS.replace("COLOR_PLACEHOLDER", color)

    title = esc(d.get("game_name", "—")) + "#" + esc(d.get("tag_line", "—"))
    now   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<header>
  <div class="brand">
    <svg class="logo" viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="16" fill="#ff4655"/>
      <polygon points="16,6 22,12 16,18 10,12" fill="white"/>
      <rect x="14" y="18" width="4" height="8" fill="white"/>
    </svg>
    <span class="name">{esc(d.get('game_name','—'))}#{esc(d.get('tag_line','—'))}</span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {badge}
    <span style="font-size:.85em;color:#8b978f">Level {d.get('level','—')}</span>
  </div>
</header>
<main>
{banner}
<div class="two-col">
  <div class="card">
    <h3>Thong tin tai khoan</h3>
    <div class="row"><span class="l">PUUID</span><span class="v sm">{esc(d.get('puuid',''))}</span></div>
    <div class="row"><span class="l">Level</span><span class="v">{d.get('level','—')}</span></div>
    <div class="row"><span class="l">Region</span><span class="v">{(d.get('region','') or '').upper()}</span></div>
    <div class="row"><span class="l">Country</span><span class="v">{(d.get('country','') or '').upper()}</span></div>
    <div class="row"><span class="l">Email Verified</span><span class="v">{email_v}</span></div>
    <div class="row"><span class="l">Phone Verified</span><span class="v">{phone_v}</span></div>
    <div class="row"><span class="l">Account Created</span><span class="v">{esc(d.get('created_at','—'))}</span></div>
    <div class="row"><span class="l">Status</span><span class="v">{status_html}</span></div>
  </div>
  <div class="card">
    <h3>Wallet & Rank</h3>
    <div class="wg">
      <div class="wc"><div class="v">{vp:,}</div><div class="l">VP</div></div>
      <div class="wc"><div class="v">{rp:,}</div><div class="l">RP</div></div>
      <div class="wc"><div class="v">{kc:,}</div><div class="l">KC</div></div>
      <div class="wc"><div class="v">{fa:,}</div><div class="l">FA</div></div>
    </div>
    <div class="row"><span class="l">Current Rank</span><span class="v">{rank}</span></div>
    <div class="row"><span class="l">Skin Levels</span><span class="v">{d.get('skins_count', 0)}</span></div>
  </div>
</div>
{tx_section}
<div style="text-align:center;color:#8b978f;font-size:.78em;margin-top:12px">Checked: {now}</div>
</main>
<footer>Valorant Checker — Auto Generated</footer>
</body>
</html>"""


def index_html(cats: dict) -> str:
    # summary boxes
    summary = ""
    for cat, cat_results in cats.items():
        color = CAT_COLORS.get(cat, "#8b978f")
        label = CAT_LABELS.get(cat, cat)
        summary += f'<div class="s" style="border-color:{color}"><div class="n" style="color:{color}">{len(cat_results)}</div><div class="l" style="color:{color}">{label}</div></div>'

    # table rows
    rows = ""
    idx = 0
    for cat, cat_results in cats.items():
        if not cat_results:
            continue
        color = CAT_COLORS.get(cat, "#8b978f")
        label = CAT_LABELS.get(cat, cat)
        rows += f'<h2><span class="dot" style="background:{color}"></span>{label} ({len(cat_results)})</h2>'
        rows += f'<table class="t"><thead><tr><th>#</th><th>Account</th><th>Level</th><th>VP</th><th>Skins</th><th>Status</th><th>File</th></tr></thead><tbody>'
        for r in cat_results:
            idx += 1
            fn   = safe_file(f"{r.get('game_name','?')}_{r.get('tag_line','?')}.html")
            href = f"{cat}/{fn}" if cat != "error" else f"error/{fn}"
            status_color = "#4caf50" if r.get("account_status") == "Active" else "#ff5252"
            rows += f"""<tr>
  <td>{idx}</td>
  <td>{esc(r.get('game_name','—'))}#{esc(r.get('tag_line','—'))}</td>
  <td>{r.get('level','—')}</td>
  <td>{(r.get('vp') or 0):,}</td>
  <td>{r.get('skins_count',0)}</td>
  <td style="color:{status_color}">{esc(r.get('account_status','Active'))}</td>
  <td><a href="{href}" download>HTML</a></td>
</tr>"""
        rows += "</tbody></table>"

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Valorant Check Results</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;padding:20px}}
h1{{color:#ff4655;font-size:1.4em;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #ff4655}}
.s{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.s div{{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:12px 16px;text-align:center}}
.s div .n{{font-size:1.3em;font-weight:700;color:#ff4655}}
.s div .l{{font-size:.72em;color:#8b978f;text-transform:uppercase}}
.cat{{margin-bottom:24px}}
.cat h2{{font-size:.85em;text-transform:uppercase;letter-spacing:.5px;color:#8b978f;margin-bottom:8px;display:flex;align-items:center;gap:8px}}
.cat h2 .dot{{width:10px;height:10px;border-radius:50%}}
.t{{width:100%;border-collapse:separate;border-spacing:0 4px}}
.t th{{text-align:left;color:#8b978f;font-size:.72em;text-transform:uppercase;padding:6px 10px}}
.t td{{background:#1a2634;padding:8px 10px;font-size:.85em;border-radius:6px}}
.t tr:hover td{{background:#243447}}
.t a{{color:#ff4655;text-decoration:none;font-weight:600}}
</style>
</head>
<body>
<h1>Valorant Bulk Check — {now}</h1>
<div class="s">{summary}</div>
<div class="cat">{rows}</div>
</body>
</html>"""


# ── save results ───────────────────────────────────────────────────────

def save_results(results: list[dict]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = OUTPUT_DIR / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cats = {"0_skin": [], "1-20_skins": [], "20-40_skins": [], "40-60_skins": [], "60-100_skins": [], "100plus_skins": [], "error": []}

    for r in results:
        if not r.get("success"):
            cats["error"].append(r)
            html = account_html({
                "game_name": r.get("username", "?"),
                "tag_line": "—",
                "account_status": r.get("error", "Error"),
                "is_banned": True,
            }, "error")
            fn = safe_file(r.get("username", "?")) + "_error.html"
            (run_dir / "error").mkdir(exist_ok=True)
            (run_dir / "error" / fn).write_text(html, encoding="utf-8")
            continue

        cat = cat_of(r.get("skins_count", 0))
        cats[cat].append(r)
        html = account_html(r, cat)
        fn = safe_file(r.get("game_name", "?")) + "_" + safe_file(r.get("tag_line", "?")) + ".html"
        (run_dir / cat).mkdir(exist_ok=True)
        (run_dir / cat / fn).write_text(html, encoding="utf-8")

    # index
    (run_dir / "index.html").write_text(index_html(cats), encoding="utf-8")

    # report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total":   len(results),
        "success": sum(1 for r in results if r.get("success")),
        "failed":  sum(1 for r in results if not r.get("success")),
        "results": results,
    }
    (run_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  📁 Ket qua: {run_dir}")
    print(f"  💡 Mo   {run_dir / 'index.html'} de xem")
    return run_dir
