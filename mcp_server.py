"""
Exposes OpsAgent's tools as an MCP (Model Context Protocol) server, so
Claude Desktop -- or any other MCP client -- can call create_task,
send_slack_alert, and draft_email directly, without going through the
Streamlit UI or the LangGraph agent at all.

This is deliberately a THIN wrapper: it reuses the exact same functions
from agent/tools.py that the LangGraph agent uses, so there is only one
real implementation of each tool, not two copies to keep in sync.

Run it:
    python mcp_server.py

Then point Claude Desktop at it (see README for the config snippet).
"""

from dotenv import load_dotenv

load_dotenv()  # so JIRA_*/NOTION_*/GROQ_* etc. are set before agent.tools imports below

from mcp.server.fastmcp import FastMCP

from agent.tools import (
    create_task as _create_task,
    search_tasks as _search_tasks,
    send_slack_alert as _send_slack_alert,
    draft_email as _draft_email,
    send_approved_email as _send_approved_email,
)

mcp = FastMCP("opsagent")


@mcp.tool()
def create_task(title: str, description: str = "", priority: str = "medium") -> dict:
    """Open a task/ticket. priority must be 'low', 'medium', or 'high'."""
    return _create_task(title, description, priority)


@mcp.tool()
def search_tasks(query: str = "") -> dict:
    """Search existing tasks by a keyword in the title or description."""
    return _search_tasks(query)


@mcp.tool()
def send_slack_alert(message: str) -> dict:
    """Post a message to the team's Slack channel (via SLACK_WEBHOOK_URL)."""
    return _send_slack_alert(message)


@mcp.tool()
def draft_email(to: str, subject: str, context: str) -> dict:
    """Draft (never sends) a professional email from a short context description."""
    return _draft_email(to, subject, context)


@mcp.tool()
def send_approved_email(to: str) -> dict:
    """Actually sends the most recent draft_email draft written to this recipient,
    via the real Gmail API. Only call this after draft_email, and only once the
    human has approved the drafted content -- this is a real, irreversible send."""
    return _send_approved_email(to)


if __name__ == "__main__":
    mcp.run(transport="stdio")
