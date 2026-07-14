"""
The core agent, built as a LangGraph state machine:

    understand -> clarify -> [ASK GATE, only if ambiguous] -> plan
        -> [HUMAN APPROVAL GATE] -> execute -> summarize

Two real interrupts:
  1. "ask_human"  -- pauses if the request is missing info the agent needs
                     (e.g. no recipient email, no priority given)
  2. "execute"    -- pauses before any tool actually runs, for approval

The graph is compiled with `interrupt_before=["ask_human", "execute"]`,
meaning LangGraph genuinely pauses at these points and hands control back
to the caller (Streamlit app / CLI). Nothing runs without a human in the loop.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.llm import chat, chat_json
from agent.tools import TOOL_REGISTRY, TOOL_DESCRIPTIONS


def understand_node(state: AgentState) -> dict:
    request = state["request"]
    intent = chat(
        system_prompt="Summarize the user's business request in one crisp sentence describing what outcome they want.",
        user_prompt=request,
    )
    trace = state.get("trace", [])
    trace.append(f"Understood request as: {intent}")
    return {"intent": intent, "trace": trace}


def clarify_node(state: AgentState) -> dict:
    """
    Checks whether the request has enough info to act on safely.
    If something essential is missing (e.g. no recipient for an email,
    no clear priority for an urgent ticket), the agent asks instead of
    guessing -- guessing is how agents create wrong tickets and send
    emails to the wrong person.
    """
    system_prompt = f"""You are a clarification-check module for a business automation agent.
Available tools:
{TOOL_DESCRIPTIONS}

Decide if the request below has enough concrete detail to plan tool calls safely.
Only ask for clarification if something ESSENTIAL is missing or genuinely ambiguous
(e.g. no recipient email/name for an email, no way to tell the priority/urgency,
the request could mean two very different things). Do not ask about minor,
inferable details -- default to reasonable assumptions where possible.

Respond ONLY with JSON:
{{"needs_clarification": true/false, "question": "one short question, or empty string"}}"""

    result = chat_json(system_prompt, state["request"])
    needs = result.get("needs_clarification", False)
    question = result.get("question", "")

    trace = state.get("trace", [])
    if needs:
        trace.append(f"Needs clarification: {question}")
    else:
        trace.append("Request has enough detail, no clarification needed.")
    return {"needs_clarification": needs, "clarifying_question": question, "trace": trace}


def ask_human_node(state: AgentState) -> dict:
    """
    No-op node that exists purely as an interrupt point. Execution pauses
    right BEFORE this node runs (see interrupt_before in build_graph), so by
    the time this function body actually executes, the caller has already
    resumed the graph after collecting the human's answer and folding it
    into state["request"] via update_state().
    """
    trace = state.get("trace", [])
    trace.append("Resumed after human clarification.")
    return {"needs_clarification": False, "trace": trace}


def route_after_clarify(state: AgentState) -> str:
    """Conditional edge: only stop for a human answer if genuinely needed."""
    return "ask_human" if state.get("needs_clarification") else "plan"


def plan_node(state: AgentState) -> dict:
    system_prompt = f"""You are a planning module for a business automation agent.
Given a request, decide which tools to call, in order, to fulfill it.

Available tools:
{TOOL_DESCRIPTIONS}

Respond ONLY with JSON in this exact shape:
{{"plan": [{{"tool": "tool_name", "args": {{...}}}}, ...]}}

Use as few tool calls as necessary. Only use tools from the list above."""

    result = chat_json(system_prompt, state["request"])
    plan = result.get("plan", [])

    trace = state.get("trace", [])
    trace.append(f"Planned {len(plan)} step(s): {[p['tool'] for p in plan]}")
    return {"plan": plan, "trace": trace, "human_approved": None}


def execute_node(state: AgentState) -> dict:
    results = []
    trace = state.get("trace", [])
    for step in state.get("plan", []):
        tool_name = step.get("tool")
        args = step.get("args", {})
        tool_fn = TOOL_REGISTRY.get(tool_name)
        if not tool_fn:
            result = {"tool": tool_name, "status": "error", "error": "unknown tool"}
        else:
            try:
                result = tool_fn(**args)
            except Exception as e:
                result = {"tool": tool_name, "status": "error", "error": str(e)}
        results.append(result)
        trace.append(f"Executed {tool_name} -> {result.get('status')}")
    return {"results": results, "trace": trace}


def summarize_node(state: AgentState) -> dict:
    summary = chat(
        system_prompt="Summarize what actions were taken for a busy stakeholder in 2-3 sentences. Be concrete.",
        user_prompt=f"Request: {state['request']}\nResults: {state.get('results')}",
    )
    trace = state.get("trace", [])
    trace.append("Generated final summary.")
    return {"summary": summary, "trace": trace}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("understand", understand_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("ask_human", ask_human_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("understand")
    graph.add_edge("understand", "clarify")
    graph.add_conditional_edges("clarify", route_after_clarify, {"ask_human": "ask_human", "plan": "plan"})
    graph.add_edge("ask_human", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "summarize")
    graph.add_edge("summarize", END)

    # Pause before asking the human a clarifying question, and again before
    # any tool actually runs -- both are human-in-the-loop gates.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["ask_human", "execute"])


# a single shared compiled graph + checkpointer for the app to reuse
compiled_graph = build_graph()
