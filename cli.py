"""
Terminal demo of OpsAgent -- useful for a quick recording/GIF for your README,
and for showing the human-approval interrupt clearly in raw form.

Usage:
    python cli.py "A customer complained their order #4521 is late. Log a ticket and draft an apology email."
"""

import sys
import uuid
from dotenv import load_dotenv

load_dotenv()

from agent.graph import compiled_graph


def main():
    if len(sys.argv) < 2:
        print('Usage: python cli.py "<your request>"')
        sys.exit(1)

    request = " ".join(sys.argv[1:])
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    print(f"\n📝 Request: {request}\n")
    print("🧠 Understanding...\n")
    compiled_graph.invoke({"request": request, "trace": []}, config=config)

    snapshot = compiled_graph.get_state(config)
    if "ask_human" in snapshot.next:
        question = snapshot.values.get("clarifying_question", "")
        print(f"❓ {question}")
        answer = input("Your answer: ").strip()
        updated_request = f"{request}\n\nClarification: {answer}"
        compiled_graph.update_state(config, {"request": updated_request})
        print("\n🧠 Planning...\n")
        compiled_graph.invoke(None, config=config)
        snapshot = compiled_graph.get_state(config)

    plan = snapshot.values.get("plan", [])
    print(f"Intent: {snapshot.values.get('intent')}\n")
    print("Proposed plan:")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step['tool']}({step.get('args', {})})")

    approve = input("\nApprove and execute this plan? [y/N] ").strip().lower()
    if approve != "y":
        print("Rejected. Nothing was executed.")
        return

    print("\n⚙️  Executing...\n")
    compiled_graph.invoke(None, config=config)

    final = compiled_graph.get_state(config).values
    print("✅ Summary:", final.get("summary"))
    print("\nTool results:")
    for r in final.get("results", []):
        print(" -", r)


if __name__ == "__main__":
    main()
