# OpsAgent — A Human-Approved AI Agent for Business Workflow Automation

OpsAgent is an AI agent that takes a plain-English business request (a support
escalation, a customer complaint, an internal ask), plans the actions needed to
resolve it, **pauses for human approval**, then executes real tool calls:
opening a task/ticket, drafting an email, and posting a Slack alert.

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
- **Slack Incoming Webhooks** — real external integration, no OAuth needed
- **JSON-backed task store** — stand-in for Jira/Notion; swap in a real API with the same function signature

## Tools the agent can call

| Tool | What it does |
|---|---|
| `create_task` | Opens a task/ticket (title, description, priority) |
| `search_tasks` | Looks up existing tasks by keyword |
| `send_slack_alert` | Posts a message to a Slack channel via webhook |
| `draft_email` | Drafts (never auto-sends) a professional email from context |

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY (free: console.groq.com/keys)

# Web UI
streamlit run app.py

# or Terminal
python cli.py "Customer said order #4521 is 5 days late. Log a ticket and draft an apology email."
```

Slack integration is optional — without `SLACK_WEBHOOK_URL` set, Slack calls
are safely simulated and logged so the whole flow still runs end-to-end.

## Example

**Request:** "Customer complained order #4521 is 5 days late. Log a ticket and draft an apology email."

**Agent proposes:**
1. `create_task(title="Late delivery - order 4521", priority="high")`
2. `draft_email(to="customer", subject="Apology for delayed order #4521", ...)`
3. `send_slack_alert(message="High-priority ticket opened for order #4521")`

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

- Swap the JSON task store for real Jira/Notion API calls
- Add Gmail API for actually sending approved drafts
- Expose the agent as an MCP server so it's usable directly from Claude Desktop
- Add multi-turn clarification when a request is ambiguous
