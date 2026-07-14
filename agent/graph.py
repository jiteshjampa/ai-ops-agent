"""
The core agent, built as a LangGraph state machine:

    understand -> plan -> [HUMAN APPROVAL GATE] -> execute -> summarize

The graph is compiled with `interrupt_before=["execute"]`, meaning LangGraph
genuinely pauses execution before taking any action and hands control back
to the caller (Streamlit app / CLI). Nothing runs until a human approves it.
This is the "safe agent" pattern real companies actually want, not a demo
that YOLOs API calls.
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
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("understand")
    graph.add_edge("understand", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "summarize")
    graph.add_edge("summarize", END)

    # Pause right before any tool actually runs -- this is the human-in-the-loop gate.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["execute"])


# a single shared compiled graph + checkpointer for the app to reuse
compiled_graph = build_graph()
