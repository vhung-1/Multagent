"""Minimal Brevo (Sendinblue) transactional email client."""
from __future__ import annotations

import requests

API_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 30


def send_email(api_key: str, sender_email: str, sender_name: str,
               recipients: list[str], subject: str, html_content: str) -> dict:
    """Send a transactional HTML email. Raises on non-2xx."""
    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not set")
    if not recipients:
        raise RuntimeError("No recipients configured (MAIL_TO)")

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": e} for e in recipients],
        "subject": subject,
        "htmlContent": html_content,
    }
    resp = requests.post(
        API_URL,
        headers={"api-key": api_key, "content-type": "application/json",
                 "accept": "application/json"},
        json=payload,
        timeout=TIMEOUT,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Brevo send failed [{resp.status_code}]: {resp.text}")
    return resp.json() if resp.content else {}
