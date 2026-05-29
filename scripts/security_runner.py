#!/usr/bin/env python3
"""Run OWASP security tests against an Agentforce agent via sf agent preview.

Usage:
    python3 scripts/security_runner.py --org <alias> --agent <AgentName> [options]

Options:
    --org           Target org alias (required)
    --agent         Agent bundle name (required)
    --mode          quick|full (default: full)
    --categories    Comma-separated category filter (default: all)
    --output        Output file path (default: stdout)
    --project-dir   Directory to run sf commands from (default: cwd)
    --delay         Seconds between tests (default: 1)

This script is an EXECUTOR only — it sends adversarial payloads and collects
responses. It does NOT judge verdicts. All evaluation is done by Claude Code
as LLM-as-judge after the runner completes (reading the output JSON).

Loads test payloads from skills/securing-agentforce/assets/payloads/*.yaml,
executes them via sf agent preview start/send/end, and outputs a JSON array
of {test_id, category, severity, name, utterances_sent, response} objects.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


PAYLOADS_DIR = Path(__file__).resolve().parent.parent / "skills" / "securing-agentforce" / "assets" / "payloads"

CATEGORY_FILES = {
    "prompt_injection": "prompt-injection.yaml",
    "sensitive_info": "sensitive-info-disclosure.yaml",
    "output_handling": "output-handling.yaml",
    "excessive_agency": "excessive-agency.yaml",
    "system_prompt_leakage": "system-prompt-leakage.yaml",
    "misinformation": "misinformation.yaml",
    "unbounded_consumption": "unbounded-consumption.yaml",
}

ALL_CATEGORIES = list(CATEGORY_FILES.keys())


def parse_yaml_tests(filepath):
    """Parse test payloads from YAML without requiring PyYAML.

    Uses simple line-by-line parsing since our YAML has a known structure.
    """
    tests = []
    if not filepath.exists():
        print(f"WARNING: Payload file not found: {filepath}", file=sys.stderr)
        return tests

    content = filepath.read_text()
    category = ""
    cat_match = re.search(r"^category:\s*(.+)$", content, re.MULTILINE)
    if cat_match:
        category = cat_match.group(1).strip()

    # Split on test boundaries (lines starting with "  - id:")
    test_blocks = re.split(r"(?=^\s{2}- id:)", content, flags=re.MULTILINE)

    for block in test_blocks:
        id_match = re.search(r"- id:\s*(.+)$", block, re.MULTILINE)
        if not id_match:
            continue

        test_id = id_match.group(1).strip()
        name_match = re.search(r"name:\s*(.+)$", block, re.MULTILINE)
        sev_match = re.search(r"severity:\s*(.+)$", block, re.MULTILINE)
        tech_match = re.search(r"technique:\s*(.+)$", block, re.MULTILINE)

        name = name_match.group(1).strip().strip('"') if name_match else test_id
        severity = sev_match.group(1).strip() if sev_match else "medium"
        technique = tech_match.group(1).strip() if tech_match else ""

        # Extract turns (user utterances)
        turns = []
        for turn_match in re.finditer(r'content:\s*"(.+?)"', block):
            turns.append(turn_match.group(1))
        # Also handle multi-line content blocks
        if not turns:
            for turn_match in re.finditer(r"content:\s*(.+)$", block, re.MULTILINE):
                val = turn_match.group(1).strip().strip('"').strip("'")
                if val:
                    turns.append(val)


        if turns:
            tests.append({
                "id": test_id,
                "category": category,
                "severity": severity,
                "name": name,
                "technique": technique,
                "turns": turns,
            })

    return tests


def load_tests(categories, mode):
    """Load tests from payload YAML files, filtered by category and mode."""
    all_tests = []
    for cat in categories:
        filename = CATEGORY_FILES.get(cat)
        if not filename:
            print(f"WARNING: Unknown category '{cat}', skipping", file=sys.stderr)
            continue
        filepath = PAYLOADS_DIR / filename
        tests = parse_yaml_tests(filepath)
        all_tests.extend(tests)

    if mode == "quick":
        all_tests = [t for t in all_tests if t["severity"] in ("critical", "high")]

    return all_tests


def run_sf(args, project_dir, timeout=60):
    """Run sf CLI command and return parsed JSON.

    Note: sf CLI output may contain control characters that break json.loads.
    We strip them before parsing (same approach as testing-agentforce).
    """
    cmd = ["sf"] + args + ["--json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=project_dir, timeout=timeout
        )
        # Strip control characters (sf CLI output contains them)
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", result.stdout)
        return json.loads(clean)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "status": 1}
    except (json.JSONDecodeError, ValueError):
        return {"error": result.stderr or result.stdout, "status": 1}


def start_session(agent, org, project_dir):
    """Start a new preview session. Returns session ID or None."""
    r = run_sf(
        ["agent", "preview", "start", "--authoring-bundle", agent, "-o", org],
        project_dir,
    )
    if r.get("status") == 0:
        return r.get("result", {}).get("sessionId")
    return None


def send_message(session_id, message, agent, org, project_dir):
    """Send a message and return the agent's response text."""
    r = run_sf(
        ["agent", "preview", "send", "--session-id", session_id,
         "--utterance", message, "--authoring-bundle", agent, "-o", org],
        project_dir,
    )
    if r.get("status") == 0:
        msgs = r.get("result", {}).get("messages", [])
        if msgs:
            return msgs[-1].get("message", msgs[-1].get("content", ""))
    # Fallback: try alternate response structures
    messages = r.get("messages", [])
    if messages:
        return messages[-1].get("content", messages[-1].get("message", ""))
    return f"ERROR: {r.get('name', r.get('error', 'unknown'))}"


def end_session(session_id, agent, org, project_dir):
    """End a preview session."""
    run_sf(
        ["agent", "preview", "end", "--session-id", session_id,
         "--authoring-bundle", agent, "-o", org],
        project_dir,
    )


def run_tests(tests, agent, org, project_dir, delay):
    """Execute all tests and return results array."""
    results = []
    total = len(tests)
    current_category = None

    print(f"Starting OWASP Security Assessment: {total} tests", file=sys.stderr)
    print(f"Agent: {agent} | Org: {org}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    for i, test in enumerate(tests):
        cat = test["category"]
        if cat != current_category:
            current_category = cat
            print(f"\n[{cat.upper()}]", file=sys.stderr)

        print(f"  [{i+1}/{total}] {test['id']}: {test['name']}...", file=sys.stderr, end=" ", flush=True)

        session = start_session(agent, org, project_dir)
        if not session:
            results.append({
                "test_id": test["id"],
                "category": cat,
                "severity": test["severity"],
                "name": test["name"],
                "response": "",
                "verdict": "INCONCLUSIVE",
                "error": "session_start_failed",
            })
            print("SKIP (no session)", file=sys.stderr)
            time.sleep(delay)
            continue

        # Send all turns, keep final response
        response = ""
        for turn in test["turns"]:
            response = send_message(session, turn, agent, org, project_dir)
            if len(test["turns"]) > 1:
                time.sleep(0.5)

        end_session(session, agent, org, project_dir)

        results.append({
            "test_id": test["id"],
            "category": cat,
            "severity": test["severity"],
            "name": test["name"],
            "technique": test.get("technique", ""),
            "utterances_sent": test["turns"],
            "response": response,
            "turns_sent": len(test["turns"]),
        })

        resp_preview = response[:50] + "..." if len(response) > 50 else response
        print(f"OK ({len(response)} chars)", file=sys.stderr)
        time.sleep(delay)

    return results



def main():
    parser = argparse.ArgumentParser(description="Run OWASP security tests against an Agentforce agent")
    parser.add_argument("--org", required=True, help="Target org alias")
    parser.add_argument("--agent", required=True, help="Agent bundle name (DeveloperName)")
    parser.add_argument("--mode", choices=["quick", "full"], default="full", help="Test mode (default: full)")
    parser.add_argument("--categories", help="Comma-separated category filter (default: all)")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument("--project-dir", default=os.getcwd(), help="SF project directory (default: cwd)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between tests (default: 1)")

    args = parser.parse_args()

    categories = ALL_CATEGORIES
    if args.categories:
        categories = [c.strip() for c in args.categories.split(",")]

    tests = load_tests(categories, args.mode)
    if not tests:
        print("ERROR: No tests loaded. Check payload files and category names.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(tests)} tests ({args.mode} mode)", file=sys.stderr)

    results = run_tests(tests, args.agent, args.org, args.project_dir, args.delay)

    # Output results
    output_json = json.dumps(results, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"\nResults saved to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    # Print summary
    errored = sum(1 for r in results if r.get("error"))
    collected = len(results) - errored
    print(f"\nDone: {collected} responses collected, {errored} errors out of {len(results)} tests", file=sys.stderr)
    print("Verdicts will be assigned by LLM-as-judge (Claude Code) on the output.", file=sys.stderr)


if __name__ == "__main__":
    main()
