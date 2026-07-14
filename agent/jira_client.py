"""
Creates real tickets in Jira via its REST API.

--- One-time setup ---
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
   and create an API token.
2. Set these three environment variables (in .env):
     JIRA_BASE_URL=https://yourcompany.atlassian.net
     JIRA_EMAIL=you@yourcompany.com
     JIRA_API_TOKEN=the token from step 1
     JIRA_PROJECT_KEY=the short project code, e.g. "OPS"

Without all four set, is_configured() returns False and tools.py falls
back to the local JSON task store instead -- the agent keeps working either way.
"""

import os
import requests
from requests.auth import HTTPBasicAuth


def is_configured() -> bool:
    return all([
        os.environ.get("JIRA_BASE_URL"),
        os.environ.get("JIRA_EMAIL"),
        os.environ.get("JIRA_API_TOKEN"),
        os.environ.get("JIRA_PROJECT_KEY"),
    ])


def create_jira_issue(title: str, description: str, priority: str = "medium") -> dict:
    base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    project_key = os.environ["JIRA_PROJECT_KEY"]

    # Jira's priority names are capitalized and don't include "medium" by
    # default in most schemes -- map our simple 3 levels to Jira's common ones.
    priority_map = {"low": "Low", "medium": "Medium", "high": "High"}

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": priority_map.get(priority, "Medium")},
        }
    }

    try:
        resp = requests.post(
            f"{base_url}/rest/api/3/issue",
            json=payload,
            auth=HTTPBasicAuth(email, token),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if not resp.ok:
            # Jira puts the actually-useful info (which field/value is invalid)
            # in the response body, not in the HTTP status line -- surface it
            # instead of a bare "400 Client Error" so failures are diagnosable.
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            return {"status": "error", "error": f"{resp.status_code} from Jira: {detail}"}

        data = resp.json()
        return {
            "status": "success",
            "issue_key": data.get("key"),
            "url": f"{base_url}/browse/{data.get('key')}",
        }
    except requests.RequestException as e:
        return {"status": "error", "error": str(e)}
