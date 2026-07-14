"""
Sends an approved email draft via the real Gmail API.

This deliberately mirrors the Slack webhook pattern already in tools.py:
if credentials aren't configured, calls are safely simulated instead of
failing, so the rest of the agent still runs end-to-end without Gmail set up.

--- One-time setup (you only do this once) ---
1. Go to https://console.cloud.google.com/ and create a project (or reuse one).
2. Enable the "Gmail API" for that project (APIs & Services -> Library).
3. Go to APIs & Services -> Credentials -> Create Credentials -> OAuth client ID.
   - Application type: Desktop app
   - Download the JSON file it gives you, save it as `credentials.json`
     in the project root (same folder as app.py).
4. Go to APIs & Services -> OAuth consent screen and add your own Gmail
   address as a "Test user" (required while the app is unpublished).
5. First time you actually send an email, this module opens a browser
   window asking you to log in and approve access. After that, it caches
   a `token.json` locally so you won't be asked again.

`credentials.json` and `token.json` both contain secrets -- they're already
in .gitignore. Never commit them.
"""

import os
import base64
from email.mime.text import MIMEText
from pathlib import Path

CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"
TOKEN_PATH = Path(__file__).parent.parent / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def is_configured() -> bool:
    return CREDENTIALS_PATH.exists()


def _get_credentials():
    """Loads cached credentials, or runs the OAuth flow if none exist yet."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def send_gmail(to: str, subject: str, body: str) -> dict:
    """
    Actually sends an email via Gmail. Requires credentials.json to be present
    (see setup steps above). Falls back to a simulated response if not configured,
    so the agent's execute_node never crashes just because Gmail isn't set up yet.
    """
    if not is_configured():
        return {
            "tool": "send_gmail",
            "status": "simulated",
            "note": "credentials.json not found -- see agent/gmail_client.py for setup steps.",
            "to": to,
            "subject": subject,
        }

    try:
        from googleapiclient.discovery import build

        creds = _get_credentials()
        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"tool": "send_gmail", "status": "success", "message_id": sent.get("id"), "to": to}

    except Exception as e:
        return {"tool": "send_gmail", "status": "error", "error": str(e)}
