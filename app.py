"""
Streamlit UI for OpsAgent.

Flow shown to the user:
1. Type a business request in plain English.
2. Agent understands it and proposes a plan (which tools it wants to call).
3. Human reviews and approves/rejects the plan -- nothing executes without this.
4. On approval, the agent executes the plan and reports back what it did.
"""

import os
import uuid
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# On Streamlit Community Cloud, secrets are set via st.secrets, not real env vars.
# Bridge them into os.environ so the rest of the app (which reads os.environ.get)
# doesn't need to know or care where it's deployed.
try:
    for _key in ["GROQ_API_KEY", "SLACK_WEBHOOK_URL"]:
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass  # no secrets.toml locally -- .env / real env vars still work fine

from agent.graph import compiled_graph

st.set_page_config(page_title="OpsAgent", page_icon="🤖", layout="centered")
st.title("🤖 OpsAgent")
st.caption("An AI agent that plans business actions, waits for your approval, then executes them.")

if not os.environ.get("GROQ_API_KEY"):
    st.warning("Set GROQ_API_KEY (in a .env file or environment variable) to run this. "
               "Free key: https://console.groq.com/keys")

def stage_from_snapshot(config) -> str:
    """LangGraph tells us which node is about to run via snapshot.next.
    We use that to decide which UI screen to show."""
    snapshot = compiled_graph.get_state(config)
    next_nodes = snapshot.next
    if "ask_human" in next_nodes:
        return "awaiting_clarification"
    if "execute" in next_nodes:
        return "awaiting_approval"
    return "done"


if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "stage" not in st.session_state:
    st.session_state.stage = "input"  # input -> awaiting_clarification? -> awaiting_approval -> done

config = {"configurable": {"thread_id": st.session_state.thread_id}}

request = st.text_area(
    "What do you need done?",
    placeholder="e.g. A customer emailed saying their order #4521 is 5 days late. "
                "Log a support ticket and draft an apology email.",
    disabled=(st.session_state.stage != "input"),
)

if st.session_state.stage == "input":
    if st.button("Plan it", type="primary", disabled=not request.strip()):
        with st.spinner("Understanding request..."):
            compiled_graph.invoke({"request": request, "trace": []}, config=config)
        st.session_state.stage = stage_from_snapshot(config)
        st.rerun()

elif st.session_state.stage == "awaiting_clarification":
    snapshot = compiled_graph.get_state(config)
    question = snapshot.values.get("clarifying_question", "")

    st.subheader("One quick question before I plan this")
    st.write(question)
    answer = st.text_input("Your answer")

    if st.button("Continue", type="primary", disabled=not answer.strip()):
        original_request = snapshot.values.get("request", "")
        updated_request = f"{original_request}\n\nClarification: {answer}"
        with st.spinner("Got it, planning..."):
            # Fold the answer into state, then resume the graph past ask_human.
            compiled_graph.update_state(config, {"request": updated_request})
            compiled_graph.invoke(None, config=config)
        st.session_state.stage = stage_from_snapshot(config)
        st.rerun()

elif st.session_state.stage == "awaiting_approval":
    snapshot = compiled_graph.get_state(config)
    plan = snapshot.values.get("plan", [])
    intent = snapshot.values.get("intent", "")

    st.subheader("Proposed plan")
    st.write(f"**Understood intent:** {intent}")
    for i, step in enumerate(plan, 1):
        st.markdown(f"**Step {i}: `{step['tool']}`**")
        st.json(step.get("args", {}))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve & Execute", type="primary"):
            with st.spinner("Executing approved plan..."):
                compiled_graph.invoke(None, config=config)  # resume from the interrupt
            st.session_state.stage = stage_from_snapshot(config)
            st.rerun()
    with col2:
        if st.button("Reject / Start over"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.stage = "input"
            st.rerun()

elif st.session_state.stage == "done":
    snapshot = compiled_graph.get_state(config)
    values = snapshot.values

    st.subheader("Done ✅")
    st.write(values.get("summary", ""))

    with st.expander("What actually happened (tool results)"):
        for r in values.get("results", []):
            st.json(r)

    with st.expander("Full execution trace"):
        for line in values.get("trace", []):
            st.text(f"• {line}")

    if st.button("New request"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.stage = "input"
        st.rerun()

st.divider()
st.caption(
    "Built with LangGraph (agent orchestration + human-in-the-loop interrupt), "
    "Groq/Llama-3 (planning + drafting), and real tool integrations "
    "(task store, Slack webhook, email drafting)."
)
