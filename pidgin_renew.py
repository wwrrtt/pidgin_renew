"""
PidginHost free server auto-renewal script (GitHub Actions ready).

Environment variables:
  PIDGIN_EMAIL       - account email
  PIDGIN_PASSWORD    - account password
  TG_BOT_TOKEN       - Telegram bot token (optional, for notifications)
  TG_CHAT_ID         - Telegram chat ID (optional, for notifications)
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from cloakbrowser import launch

LOGIN_URL = "https://www.pidginhost.com/panel/account/login"
PANEL_URL = "https://www.pidginhost.com/panel/"


def send_telegram(text: str) -> bool:
    """Send a markdown message via Telegram bot. Returns True on success."""
    token = os.environ.get("TG_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TG_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[TG] Skipped — TG_BOT_TOKEN or TG_CHAT_ID not set")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            print("[TG] Notification sent")
            return True
        else:
            print(f"[TG] Failed (HTTP {resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[TG] Error: {e}")
        return False


def extract_days(text: str) -> int | None:
    m = re.search(r"(\d+)\s+days?", text)
    return int(m.group(1)) if m else None


def extract_server_name(text: str) -> str:
    """Pick the server name from the page breadcrumb area."""
    m = re.search(r"Cloud\s*/\s*(\S+)", text)
    return m.group(1) if m else "unknown"


def main():
    email = os.environ.get("PIDGIN_EMAIL", "").strip()
    password = os.environ.get("PIDGIN_PASSWORD", "").strip()

    if not email or not password:
        print("ERROR: PIDGIN_EMAIL and PIDGIN_PASSWORD must be set")
        sys.exit(1)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    result = {"status": "unknown", "old_days": None, "new_days": None,
              "server": None, "error": None, "duration_s": None}
    t0 = time.monotonic()

    print("Launching headless browser...")
    browser = launch(headless=True)
    page = browser.new_page()

    try:
        # ── Login: email step ──────────────────────────────────────────
        print("[1/6] Login — email")
        page.goto(LOGIN_URL, wait_until="networkidle")
        page.fill('input[type="email"][name="email"]', email)
        page.locator("button[type='submit']").filter(has_text="Log in").first.click()
        page.wait_for_timeout(2_000)

        # ── Login: password step ───────────────────────────────────────
        print("[2/6] Login — password")
        pwd = page.locator('input[type="password"][name="password"]')
        page.wait_for_selector('input[type="password"][name="password"]', timeout=10_000)
        pwd.fill(password)
        pwd.press("Enter")

        # ── Wait for redirect ──────────────────────────────────────────
        print("[3/6] Waiting for redirect...")
        for i in range(15):
            time.sleep(1)
            if page.url.rstrip("/") == PANEL_URL.rstrip("/"):
                break
        else:
            result["status"] = "login_failed"
            result["error"] = f"Stuck at {page.url}"
            raise RuntimeError(f"Login redirect failed: {page.url}")

        # ── Click Manage ───────────────────────────────────────────────
        print("[4/6] Entering server management...")
        page.locator('a:has-text("Manage")').first.click()
        page.wait_for_timeout(3_000)

        # ── Read expiry ────────────────────────────────────────────────
        print("[5/6] Reading expiry...")
        page.wait_for_selector(':has-text("This free server expires in")', timeout=10_000)
        old_text = page.locator(':has-text("This free server expires in")').first.inner_text().strip()
        result["old_days"] = extract_days(old_text)
        result["server"] = extract_server_name(old_text)
        print(f"  Server: {result['server']}, days: {result['old_days']}")

        # ── Click Extend ───────────────────────────────────────────────
        print("[6/6] Clicking 'Extend 30 days'...")
        page.locator('button:has-text("Extend 30 days")').click()
        page.wait_for_timeout(5_000)

        # ── Verify ─────────────────────────────────────────────────────
        new_text = page.locator(':has-text("This free server expires in")').first.inner_text().strip()
        result["new_days"] = extract_days(new_text)
        print(f"  New days: {result['new_days']}")

        if result["new_days"] is not None and result["old_days"] is not None:
            if result["new_days"] > result["old_days"]:
                result["status"] = "success"
            elif result["new_days"] == result["old_days"]:
                result["status"] = "unchanged"
                result["error"] = "Days didn't change — already at max or rate-limited"
            else:
                result["status"] = "regression"
                result["error"] = f"Days decreased ({result['old_days']} → {result['new_days']})"
        elif result["new_days"] == 30:
            result["status"] = "success"
        else:
            result["status"] = "parse_error"
            result["error"] = f"Cannot parse days from: {new_text[:200]}"

    except Exception as e:
        if not result["error"]:
            result["error"] = str(e)
        if result["status"] == "unknown":
            result["status"] = "exception"

    finally:
        browser.close()
        result["duration_s"] = round(time.monotonic() - t0, 1)

    # ── Build Telegram message ─────────────────────────────────────────
    status_emoji = {
        "success": "✅", "unchanged": "⚠️", "regression": "❌",
        "login_failed": "🔒", "parse_error": "🐛", "exception": "💥",
        "unknown": "❓",
    }
    emoji = status_emoji.get(result["status"], "❓")

    server = result["server"] or "unknown"
    old_d = result["old_days"]
    new_d = result["new_days"]
    dur = result["duration_s"]
    err = result["error"]

    md = (
        f"{emoji} *PidginHost Renew — {result['status'].replace('_', ' ').title()}*\n\n"
        f"🖥 Server: `{server}`\n"
        f"📅 Before: `{old_d}` days  →  After: `{new_d}` days\n"
        f"⏱ Duration: `{dur}s`\n"
        f"🕐 UTC: `{now_utc}`\n"
    )
    if err:
        md += f"\n⚠️ `{err}`"

    print("\n" + md)
    send_telegram(md)

    if result["status"] in ("success", "unchanged"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
