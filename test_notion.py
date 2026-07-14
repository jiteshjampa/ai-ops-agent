"""
Standalone Notion connection test -- isolates the Notion call from the
rest of the agent so you can debug it directly.

Run it:
    python test_notion.py
"""

from dotenv import load_dotenv

load_dotenv()

from agent.notion_client import is_configured, create_notion_task

if not is_configured():
    print("NOT CONFIGURED -- NOTION_API_KEY or NOTION_DATABASE_ID is missing from your .env")
else:
    print("Config looks present. Attempting to create a test page...")
    result = create_notion_task(
        title="[TEST] OpsAgent connection check",
        description="This is a test page created by test_notion.py to verify the Notion integration works.",
        priority="low",
    )
    print(result)
