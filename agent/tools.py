"""
Real, callable tools the agent can invoke. This is the "integrate AI with
internal systems, APIs, and business applications" part of the brief.

- create_task        -> a lightweight JSON-backed task store (stand-in for Jira/Notion)
- send_slack_alert    -> a REAL Slack Incoming Webhook call (no OAuth needed)
- draft_email         -> LLM-generated email draft, saved to disk
- search_tasks        -> query the task store

Swap create_task/search_tasks for real Jira/Notion API calls later --
the function signatures are deliberately kept provider-agnostic so that's
a drop-in change, not a rewrite.
"""

import os
import json
import uuid
import requests
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
TASKS_FILE = DATA_DIR / "tasks.json"
DRAFTS_FILE = DATA_DIR / "email_drafts.json"


def _load(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _save(path: Path, data: list) -> None:
    path.write_text(json.dumps(data, indent=2))


def create_task(title: str, description: str = "", priority: str = "medium") -> dict:
    """Creates a task/ticket. Stand-in for Jira/Notion/Linear API."""
    tasks = _load(TASKS_FILE)
    task = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tasks.append(task)
    _save(TASKS_FILE, tasks)
    return {"tool": "create_task", "status": "success", "task": task}


def search_tasks(query: str = "") -> dict:
    """Searches existing tasks by a simple substring match on title/description."""
    tasks = _load(TASKS_FILE)
    if query:
        query_lower = query.lower()
        tasks = [
            t for t in tasks
            if query_lower in t["title"].lower() or query_lower in t["description"].lower()
        ]
    return {"tool": "search_tasks", "status": "success", "count": len(tasks), "tasks": tasks}


def send_slack_alert(message: str) -> dict:
    """
    Posts to a real Slack channel via an Incoming Webhook.
    Set SLACK_WEBHOOK_URL to a real webhook (Slack -> Apps -> Incoming Webhooks)
    to actually post. Without it, the call is safely simulated so the demo
    still runs end-to-end.
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return {
            "tool": "send_slack_alert",
            "status": "simulated",
            "note": "SLACK_WEBHOOK_URL not set — message logged instead of sent.",
            "message": message,
        }

    try:
        resp = requests.post(webhook_url, json={"text": message}, timeout=10)
        resp.raise_for_status()
        return {"tool": "send_slack_alert", "status": "success", "message": message}
    except requests.RequestException as e:
        return {"tool": "send_slack_alert", "status": "error", "error": str(e)}


def draft_email(to: str, subject: str, context: str) -> dict:
    """
    Uses the LLM to draft an email body from context, and saves it to disk
    as a draft (does not send). This mirrors how a real assistant should
    behave -- draft for human review, never auto-send external comms.
    """
    from agent.llm import chat  # local import avoids a hard dependency for tools-only tests

    system_prompt = (
        "You write short, professional business emails. "
        "Return only the email body text, no subject line, no markdown."
    )
    user_prompt = f"Recipient: {to}\nSubject: {subject}\nContext: {context}\n\nDraft the email body."
    body = chat(system_prompt, user_prompt)

    drafts = _load(DRAFTS_FILE)
    draft = {
        "id": str(uuid.uuid4())[:8],
        "to": to,
        "subject": subject,
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    drafts.append(draft)
    _save(DRAFTS_FILE, drafts)
    return {"tool": "draft_email", "status": "drafted_not_sent", "draft": draft}


# Registry the planner/executor nodes use to look up tools by name.
TOOL_REGISTRY = {
    "create_task": create_task,
    "search_tasks": search_tasks,
    "send_slack_alert": send_slack_alert,
    "draft_email": draft_email,
}

TOOL_DESCRIPTIONS = """
- create_task(title, description, priority): opens a task/ticket. priority is "low"|"medium"|"high".
- search_tasks(query): searches existing tasks by keyword.
- send_slack_alert(message): posts a message to the team Slack channel.
- draft_email(to, subject, context): drafts (does not send) a professional email.
"""
