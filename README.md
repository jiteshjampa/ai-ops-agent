# OpsAgent — A Human-Approved AI Agent for Business Workflow Automation

OpsAgent is an AI agent that takes a plain-English business request (a support
escalation, a customer complaint, an internal ask), plans the actions needed to
resolve it, **pauses for human approval**, then executes real tool calls:
opening a task/ticket, drafting an email.

Built to demonstrate agentic AI + workflow automation with real business
impact — not just an LLM wrapper.

## Why it's built this way

Most "AI agent" demos let the model call tools freely, which is exactly what
you don't want in a real company. OpsAgent uses **LangGraph's interrupt
mechanism** to genuinely halt execution before any tool runs, so a human
always signs off on the plan first. This is the pattern real internal-tools
teams actually use.

```
 understand request → plan tool calls → [ HUMAN APPROVAL GATE ] → execute → summarize
```

## Stack

- **LangGraph** — stateful agent orchestration with a real human-in-the-loop interrupt (`interrupt_before`)
- **Groq / Llama-3** — fast, free-tier LLM for understanding, planning, and drafting
- **Streamlit** — approval UI
- **JSON-backed task store** — stand-in for Jira/Notion; swap in a real API with the same function signature

## Tools the agent can call

| Tool | What it does |
|---|---|
| `create_task` | Opens a task. Tries Jira, then Notion, then falls back to a local JSON store, depending on what's configured |
| `search_tasks` | Looks up existing local tasks by keyword |
| `draft_email` | Drafts (never auto-sends) a professional email from context |
| `send_approved_email` | Actually sends a previously drafted email, via the real Gmail API |

All of Jira, Notion, and Gmail are optional. Nothing is hardcoded to require them —
each one gracefully falls back to a simulated/local response if not configured,
so the agent runs end-to-end with zero external accounts if you just want to
try it out.

## Multi-turn clarification

Before planning, the agent checks whether the request has enough detail to act
on safely. If something essential is missing (a recipient with no name, a
priority that's genuinely unclear), it pauses — via a second LangGraph
interrupt, the same mechanism as the approval gate — and asks a single
clarifying question instead of guessing. Try a vague request like "handle the
thing with the client" to see it trigger.

## MCP server

`mcp_server.py` exposes the same four tools directly to Claude Desktop (or any
MCP client), reusing the exact functions from `agent/tools.py` — there's only
one implementation of each tool, not a separate copy for the agent vs. the
MCP server.

```bash
python mcp_server.py
```

To connect it to Claude Desktop, add this to your Claude Desktop config
(`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "opsagent": {
      "command": "python",
      "args": ["/absolute/path/to/ai-ops-agent/mcp_server.py"]
    }
  }
}
```

## Connecting real integrations

Each integration is optional and independently configured via `.env`:

- **Jira** — see setup steps at the top of `agent/jira_client.py`
- **Notion** — see setup steps at the top of `agent/notion_client.py`
- **Gmail** — see setup steps at the top of `agent/gmail_client.py` (needs a
  `credentials.json` file, not just an env var, since it uses OAuth)

`create_task` checks Jira, then Notion, then falls back to the local JSON
store — whichever is configured first wins, so you only need to set up the
one you actually use.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY (free: console.groq.com/keys)

# Web UI
streamlit run app.py

# or Terminal
python cli.py "Customer said order #4521 is 5 days late. Log a ticket and draft an apology email."
```

## Example

**Request:** "Customer complained order #4521 is 5 days late. Log a ticket and draft an apology email."

**Agent proposes:**
1. `create_task(title="Late delivery - order 4521", priority="high")`
2. `draft_email(to="customer", subject="Apology for delayed order #4521", ...)`

**→ waits for approval →** executes → reports back what was actually done.

## What this demonstrates

- Multi-step agent planning and execution, not a single prompt-response call
- A real human-in-the-loop safety gate before any action is taken
- Real external API integration (Slack)
- Clean separation between planning (LLM) and execution (deterministic tools) —
  the LLM decides *what* to do, code decides *how* it's done
- Extensible tool registry — adding a new integration (Jira, Notion, Gmail) means
  writing one function and registering it, no changes to the agent core

## Next steps (roadmap)

- Persist the LangGraph checkpointer to SQLite instead of in-memory, so
  in-progress approvals survive a container restart
- Add more MCP client integrations (Google Workspace, Jira, Notion directly
  as MCP servers instead of custom API wrappers)
- Multi-step clarification (currently asks at most one question per request)
