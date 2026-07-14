"""
Creates real pages (as tasks) in a Notion database via its REST API.

--- One-time setup ---
1. Go to https://www.notion.so/my-integrations and create a new integration,
   copy its "Internal Integration Secret".
2. In Notion, create (or pick) a database for tasks with at least these
   properties: "Name" (title), "Priority" (select: Low/Medium/High),
   "Description" (rich text).
3. Open that database in Notion, click "..." -> "Connections" -> add
   your integration so it has access.
4. Copy the database ID from its URL:
   notion.so/yourworkspace/DATABASE_ID?v=...
5. Set in .env:
     NOTION_API_KEY=the secret from step 1
     NOTION_DATABASE_ID=the id from step 4

Without both set, is_configured() returns False and tools.py falls back
to the local JSON task store instead.
"""

import os
import requests

NOTION_VERSION = "2022-06-28"


def is_configured() -> bool:
    return all([os.environ.get("NOTION_API_KEY"), os.environ.get("NOTION_DATABASE_ID")])


def create_notion_task(title: str, description: str, priority: str = "medium") -> dict:
    api_key = os.environ["NOTION_API_KEY"]
    database_id = os.environ["NOTION_DATABASE_ID"]
    priority_map = {"low": "Low", "medium": "Medium", "high": "High"}

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Priority": {"select": {"name": priority_map.get(priority, "Medium")}},
            "Description": {"rich_text": [{"text": {"content": description}}]},
        },
    }

    try:
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if not resp.ok:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            return {"status": "error", "error": f"{resp.status_code} from Notion: {detail}"}

        data = resp.json()
        return {"status": "success", "page_id": data.get("id"), "url": data.get("url")}
    except requests.RequestException as e:
        return {"status": "error", "error": str(e)}
