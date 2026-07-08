import json

import requests


BASE_URL = "http://localhost:8014"


def print_response(response):
    print(f"HTTP {response.status_code}")
    try:
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except requests.exceptions.JSONDecodeError:
        print(response.text)


def main():
    run_response = requests.post(
        f"{BASE_URL}/v1/assistant/run",
        json={
            "question": "Summarize the key points in this private document and cite the supporting evidence.",
            "session_id": "demo-session",
            "review_policy": "auto",
        },
        timeout=120,
    )
    print_response(run_response)
    run_response.raise_for_status()

    run_payload = run_response.json()
    if run_payload.get("status") != "waiting_feedback":
        return

    task_id = run_payload["task_id"]
    feedback_response = requests.post(
        f"{BASE_URL}/v1/assistant/feedback",
        json={
            "task_id": task_id,
            "approved": False,
            "feedback": "Please keep the answer structured with conclusion, basis, citations, and evidence gaps.",
        },
        timeout=120,
    )
    print_response(feedback_response)
    feedback_response.raise_for_status()


if __name__ == "__main__":
    main()
