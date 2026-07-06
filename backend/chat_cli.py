import argparse
import json
import uuid

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8014"


def print_json(label: str, payload):
    print(f"\n{label}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_assistant(base_url: str, question: str, session_id: str, review_policy: str):
    response = requests.post(
        f"{base_url}/v1/assistant/run",
        json={
            "question": question,
            "session_id": session_id,
            "review_policy": review_policy,
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def submit_feedback(base_url: str, task_id: str, approved: bool, feedback: str):
    response = requests.post(
        f"{base_url}/v1/assistant/feedback",
        json={
            "task_id": task_id,
            "approved": approved,
            "feedback": feedback,
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def fetch_memory(base_url: str, session_id: str):
    response = requests.get(
        f"{base_url}/v1/memory/sessions/{session_id}",
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Interactive chat CLI for the Knowledge Assistant service."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Assistant service base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--session-id",
        default=f"chat-{uuid.uuid4().hex[:8]}",
        help="Conversation session id. Reuse the same id for multi-turn chat.",
    )
    parser.add_argument(
        "--review-policy",
        choices=["auto", "always", "never"],
        default="auto",
        help="Human review policy sent to the API.",
    )
    return parser


def print_help_text(session_id: str, base_url: str, review_policy: str):
    print("Knowledge Assistant Chat CLI")
    print(f"base_url: {base_url}")
    print(f"session_id: {session_id}")
    print(f"review_policy: {review_policy}")
    print("Type your question and press Enter.")
    print("Commands: /memory, /session, /help, /exit")


def main():
    args = build_parser().parse_args()
    print_help_text(args.session_id, args.base_url, args.review_policy)

    while True:
        try:
            question = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting chat.")
            break

        if not question:
            continue

        if question in {"/exit", "/quit"}:
            print("Exiting chat.")
            break
        if question == "/help":
            print_help_text(args.session_id, args.base_url, args.review_policy)
            continue
        if question == "/session":
            print(f"Current session_id: {args.session_id}")
            continue
        if question == "/memory":
            try:
                memory_payload = fetch_memory(args.base_url, args.session_id)
                print_json("Session Memory", memory_payload)
            except requests.RequestException as exc:
                print(f"Failed to load memory: {exc}")
            continue

        try:
            run_payload = run_assistant(
                base_url=args.base_url,
                question=question,
                session_id=args.session_id,
                review_policy=args.review_policy,
            )
        except requests.RequestException as exc:
            print(f"Request failed: {exc}")
            continue

        print(f"\nTask ID: {run_payload.get('task_id', '')}")
        print(f"Status: {run_payload.get('status', '')}")
        print(f"Review Decision: {run_payload.get('review_decision', '')}")
        review_metrics = run_payload.get("review_metrics", {})
        if review_metrics:
            print_json("Review Metrics", review_metrics)

        retrieved_evidence = run_payload.get("retrieved_evidence", [])
        if retrieved_evidence:
            print_json("Retrieved Evidence", retrieved_evidence)
        else:
            retrieved_context = run_payload.get("retrieved_context", "")
            if retrieved_context:
                print("\nRetrieved Context")
                print(retrieved_context)

        draft = run_payload.get("draft", "")
        if draft:
            print("\nAssistant")
            print(draft)

        if run_payload.get("status") != "waiting_feedback":
            continue

        while True:
            feedback_action = input("\nApprove this answer? [y/n]: ").strip().lower()
            if feedback_action in {"y", "yes"}:
                approved = True
                feedback = input("Optional feedback (press Enter to skip): ").strip()
                break
            if feedback_action in {"n", "no"}:
                approved = False
                feedback = input("Feedback for revision: ").strip()
                if not feedback:
                    feedback = "Please revise the answer."
                break
            print("Please enter y or n.")

        try:
            feedback_payload = submit_feedback(
                base_url=args.base_url,
                task_id=run_payload["task_id"],
                approved=approved,
                feedback=feedback,
            )
        except requests.RequestException as exc:
            print(f"Feedback request failed: {exc}")
            continue

        print("\nFinal Answer")
        print(feedback_payload.get("answer", ""))
        if feedback_payload.get("answer_payload"):
            print_json("Final Answer Payload", feedback_payload["answer_payload"])
        report_path = feedback_payload.get("report_path")
        if report_path:
            print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
