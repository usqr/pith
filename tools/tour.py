#!/usr/bin/env python3
"""
Pith tour state manager.
Tracks which step the user is on, completion, and history.

Usage:
  python3 tour.py --action get          # get current step
  python3 tour.py --step 3 --action set # set current step
  python3 tour.py --action complete     # mark tour done
  python3 tour.py --action reset        # reset to step 1
  python3 tour.py --action status       # full status JSON
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PITH_DIR = Path.home() / ".pith"
STATE_PATH = PITH_DIR / "state.json"

STEPS = [
    {"n": 1, "name": "Tool Output Compression",  "slug": "compression"},
    {"n": 2, "name": "Live Token Meter",          "slug": "meter"},
    {"n": 3, "name": "Output Compression",        "slug": "output-modes"},
    {"n": 4, "name": "Structured Formats",        "slug": "formats"},
    {"n": 5, "name": "Token Budget",              "slug": "budget"},
    {"n": 6, "name": "Wiki — Saving",             "slug": "wiki-save"},
    {"n": 7, "name": "Wiki — Querying",           "slug": "wiki-query"},
]

TOTAL = len(STEPS)


def project_key():
    cwd = os.environ.get("CLAUDE_CWD") or os.getcwd()
    import base64
    raw = base64.b64encode(cwd.encode()).decode().replace("=", "").replace("/", "").replace("+", "")
    return "proj_" + raw[:20]


def load_state():
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return {}


def save_state(updates: dict):
    PITH_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    state.update(updates)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def load_tour_state():
    state = load_state()
    key = project_key()
    proj = state.get(key, {})
    return proj.get("tour", {})


def save_tour_state(updates: dict):
    state = load_state()
    key = project_key()
    proj = state.get(key, {})
    tour = proj.get("tour", {})
    tour.update(updates)
    proj["tour"] = tour
    state[key] = proj
    STATE_PATH.write_text(json.dumps(state, indent=2))


def get_current_step(tour: dict) -> int:
    return tour.get("current_step", 1)


def format_step_card(step_n: int) -> str:
    step = next((s for s in STEPS if s["n"] == step_n), None)
    if not step:
        return f"[PITH TOUR: step {step_n} not found]"
    return (
        f"PITH TOUR — Step {step_n}/{TOTAL}: {step['name']}\n"
        f"Completed steps: {', '.join(str(s) for s in range(1, step_n)) or 'none'}"
    )


def format_status(tour: dict) -> str:
    current = get_current_step(tour)
    completed = tour.get("completed_steps", [])
    done = tour.get("complete", False)

    lines = [
        "PITH TOUR STATUS",
        f"  Complete:      {'yes' if done else 'no'}",
        f"  Current step:  {current}/{TOTAL}",
        f"  Steps done:    {', '.join(str(s) for s in completed) if completed else 'none'}",
        f"  Started:       {tour.get('started_at', 'not yet')}",
    ]
    if done:
        lines.append(f"  Finished:      {tour.get('finished_at', 'unknown')}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Pith tour state manager")
    parser.add_argument("--step", type=int, help="Step number (1-7)")
    parser.add_argument("--action", choices=["get", "set", "complete", "reset", "status"],
                        default="get", help="Action to perform")
    args = parser.parse_args()

    tour = load_tour_state()

    if args.action == "get":
        step = get_current_step(tour)
        print(format_step_card(step))

    elif args.action == "set":
        if args.step is None:
            print("[PITH TOUR: --step required for set action]", file=sys.stderr)
            sys.exit(1)
        n = args.step
        if not (1 <= n <= TOTAL):
            print(f"[PITH TOUR: step must be 1–{TOTAL}]", file=sys.stderr)
            sys.exit(1)

        updates = {"current_step": n}
        if not tour.get("started_at"):
            updates["started_at"] = datetime.now().isoformat()

        # Mark previous steps as completed
        completed = set(tour.get("completed_steps", []))
        for s in range(1, n):
            completed.add(s)
        updates["completed_steps"] = sorted(completed)

        save_tour_state(updates)
        print(format_step_card(n))

    elif args.action == "complete":
        completed = set(tour.get("completed_steps", []))
        for s in range(1, TOTAL + 1):
            completed.add(s)
        save_tour_state({
            "complete": True,
            "current_step": TOTAL,
            "completed_steps": sorted(completed),
            "finished_at": datetime.now().isoformat(),
        })
        print(f"PITH TOUR: complete. All {TOTAL} steps finished.")

    elif args.action == "reset":
        save_tour_state({
            "current_step": 1,
            "completed_steps": [],
            "complete": False,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
        })
        print("PITH TOUR: reset to step 1.")

    elif args.action == "status":
        tour = load_tour_state()
        print(format_status(tour))


if __name__ == "__main__":
    main()
