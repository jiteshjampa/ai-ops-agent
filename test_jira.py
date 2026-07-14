"""
Standalone Jira connection test -- isolates the Jira call from the rest of
the agent so you can debug it directly without going through the Streamlit
UI or the LLM planner.

Run it:
    python test_jira.py
"""

from dotenv import load_dotenv

load_dotenv()

from agent.jira_client import is_configured, create_jira_issue

if not is_configured():
    print("NOT CONFIGURED -- one of JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN / "
          "JIRA_PROJECT_KEY is missing from your .env")
else:
    print("Config looks present. Attempting to create a test issue...")
    result = create_jira_issue(
        title="[TEST] OpsAgent connection check",
        description="This is a test issue created by test_jira.py to verify the Jira integration works.",
        priority="low",
    )
    print(result)
