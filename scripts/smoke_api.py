from __future__ import annotations

import json
import sys
import time
import urllib.request


BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"

CASES = [
    {
        "preset_id": "developer",
        "question": "Postgres vs MongoDB for a 3-person team, 6-month MVP",
        "options": ["Postgres", "MongoDB"],
        "constraints": {"team_size": 3, "timeline": "6 months"},
    },
    {
        "preset_id": "education",
        "question": "Should a student learn Rust or Go?",
        "options": ["Rust", "Go"],
        "constraints": {"team_size": 1, "timeline": "3 months"},
    },
    {
        "preset_id": "startup",
        "question": "Should our startup choose subscription or one-time pricing?",
        "options": ["Subscription", "One-time pricing"],
        "constraints": {"team_size": 4, "timeline": "6 months", "budget": "lean"},
    },
]


def request_json(method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    presets = request_json("GET", "/presets")
    print(f"presets: {[preset['preset_id'] for preset in presets]}")

    for case in CASES:
        created = request_json("POST", "/debate", case)
        debate_id = created["debate_id"]
        for _ in range(40):
            result = request_json("GET", f"/debate/{debate_id}/result")
            if result["status"] == "complete":
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"{debate_id} did not complete")
        print(f"{case['preset_id']}: {debate_id} -> {result['consensus']['winning_option']}")


if __name__ == "__main__":
    main()

