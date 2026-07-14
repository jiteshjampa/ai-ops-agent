"""
Shared state object passed between every node in the LangGraph agent.
Each node reads from and writes to this dict-like state.
"""

from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict, total=False):
    # the raw natural-language request from the user/stakeholder
    request: str

    # structured understanding of what the user actually wants
    intent: str

    # ordered list of planned tool calls, e.g.
    # [{"tool": "create_task", "args": {...}}, {"tool": "send_slack_alert", "args": {...}}]
    plan: List[Dict[str, Any]]

    # whether a human has approved the plan before execution
    human_approved: Optional[bool]

    # results returned by each tool after execution
    results: List[Dict[str, Any]]

    # final natural-language summary shown back to the user
    summary: str

    # free-form log of what happened at each step, useful for debugging/demo
    trace: List[str]
