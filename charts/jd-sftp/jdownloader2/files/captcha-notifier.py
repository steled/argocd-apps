"""Telegram notifier for pending JDownloader captchas.

Polls JDownloader's local API (RemoteAPI "Deprecated Api", port 3128) and sends
one Telegram message per new captcha. Standard library only.
"""
import html
import json
import logging
import os
import time
import urllib.error
import urllib.request

JD_API_URL = os.environ.get("JD_API_URL", "http://jdownloader2-api:3128").rstrip("/")
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))
SOLVE_URL = os.environ.get("SOLVE_URL", "https://my.jdownloader.org/")

CHALLENGE_NAMES = {
    "HCaptchaChallenge": "hCaptcha",
    "RecaptchaV2Challenge": "reCAPTCHA",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("captcha-notifier")


def jd_captchas():
    with urllib.request.urlopen(JD_API_URL + "/captcha/list", timeout=10) as resp:
        body = json.load(resp)
    # The local API wraps results as {"data": [...]}.
    if isinstance(body, dict):
        return body.get("data") or []
    return body or []


def send_telegram(text):
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def format_message(captcha):
    kind = captcha.get("type") or captcha.get("challengeType") or "Captcha"
    kind = CHALLENGE_NAMES.get(kind, kind)
    hoster = captcha.get("hoster") or "unbekannt"
    remaining_ms = captcha.get("remaining")
    lines = [f"🧩 <b>Neues Captcha</b>: {html.escape(kind)} bei <b>{html.escape(hoster)}</b>"]
    if isinstance(remaining_ms, (int, float)) and remaining_ms > 0:
        lines.append(f"Läuft in {max(1, round(remaining_ms / 60000))} Min. ab.")
    lines.append(f'<a href="{html.escape(SOLVE_URL, quote=True)}">In MyJDownloader öffnen</a>')
    return "\n".join(lines)


def main():
    log.info("watching %s every %ss", JD_API_URL, POLL_INTERVAL)
    notified = set()
    jd_reachable = True
    while True:
        try:
            captchas = jd_captchas()
            if not jd_reachable:
                log.info("JDownloader API reachable again")
                jd_reachable = True
        except (urllib.error.URLError, OSError, ValueError) as e:
            if jd_reachable:
                log.warning("JDownloader API not reachable: %s", e)
                jd_reachable = False
            time.sleep(POLL_INTERVAL)
            continue

        current = {c.get("id"): c for c in captchas if c.get("id") is not None}
        for captcha_id, captcha in current.items():
            if captcha_id in notified:
                continue
            try:
                send_telegram(format_message(captcha))
                notified.add(captcha_id)
                log.info("notified captcha %s (%s)", captcha_id, captcha.get("hoster"))
            except (urllib.error.URLError, OSError) as e:
                log.warning("Telegram send failed for captcha %s: %s", captcha_id, e)
        # Forget solved/expired captchas so the set does not grow forever.
        notified &= current.keys()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
