"""Pull-mode chaos runs for CI: MockCard plans and signs; this delivers the events to your app (which
MockCard can't reach) with the planned timing — deliveries due together go out concurrently — runs
your outcome assertions, and reports everything back to be scored.

Author: Arixeva Labs <hello@arixevalabs.com>
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from .client import MockCard

Assertion = Callable[[dict], Any]


def _deliver(target: str, delivery: dict, timeout_ms: int) -> dict:
    """Delivers one event and returns what the app answered."""
    started = time.monotonic()
    req = urllib.request.Request(target, data=delivery["body"].encode(), method="POST", headers={"Content-Type": "application/json", **delivery["headers"]})
    result: dict = {"delivery_id": delivery["id"]}
    try:
        with urllib.request.urlopen(req, timeout=timeout_ms / 1000) as res:
            result["status_code"] = res.status
    except urllib.error.HTTPError as err:
        result["status_code"] = err.code
    except Exception as err:  # noqa: BLE001 — any failure is a failed delivery
        result["status_code"] = None
        result["error"] = str(err)
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    return result


def deliver_all(deliveries: list[dict], target: str, timeout_ms: int = 10_000, sleep: Callable[[float], None] = time.sleep, send: Optional[Callable[[str, dict], dict]] = None) -> list[dict]:
    """Delivers planned events at their offsets.

    Args:
        deliveries: Planned deliveries from the API.
        target: Your webhook URL.
        timeout_ms: Per-delivery timeout.
        sleep: Waits (seconds); injectable for tests.
        send: fn(target, delivery) -> result; injectable for tests.

    Returns:
        One result per delivery, in delivery order.
    """
    send = send or (lambda t, d: _deliver(t, d, timeout_ms))
    batches: dict[int, list[dict]] = {}
    for d in deliveries:
        batches.setdefault(d["at_ms"], []).append(d)
    results: list[dict] = []
    elapsed = 0
    for at in sorted(batches):
        if at > elapsed:
            sleep((at - elapsed) / 1000)
        elapsed = at
        with ThreadPoolExecutor(max_workers=len(batches[at])) as pool:
            results.extend(pool.map(lambda d: send(target, d), batches[at]))
    return results


def _run_assertions(expectations: list[dict], deliveries: list[dict], results: list[dict], assertions: dict[str, dict[str, Assertion]]) -> list[dict]:
    """Runs your assertions per scenario; an exception fails with its message."""
    out = []
    for exp in expectations:
        scenario = exp["scenario"]
        mine = [{"delivery": d, "result": r} for d, r in zip(deliveries, results) if d["scenario"] == scenario]
        ctx = {"scenario": scenario, "expectation": exp["expectation"], "deliveries": mine, "events": [json.loads(x["delivery"]["body"]) for x in mine]}
        for name, check in (assertions.get(scenario) or {}).items():
            try:
                verdict = check(ctx)
                out.append({"scenario": scenario, "name": name, "passed": True} if verdict is True else {"scenario": scenario, "name": name, "passed": False, "message": verdict if isinstance(verdict, str) else "Assertion returned False"})
            except Exception as err:  # noqa: BLE001
                out.append({"scenario": scenario, "name": name, "passed": False, "message": str(err)})
    return out


def run_chaos(client: MockCard, project_id: str, target: str, scenarios: Optional[list[str]] = None, assertions: Optional[dict[str, dict[str, Assertion]]] = None, time_scale: Optional[float] = None, **deliver_options: Any) -> dict:
    """Runs plan → deliver → assert → report.

    Args:
        client: A MockCard client (CI or account key).
        project_id: The project.
        target: Your webhook URL as the app sees it, e.g. http://127.0.0.1:8000/webhooks/stripe/.
        scenarios: Scenarios to run (None = MockCard's default set).
        assertions: {scenario: {name: fn(ctx) -> True | False | "message"}}.
        time_scale: 0–1, shrinks waits for fast CI.
        **deliver_options: timeout_ms, sleep, send (see deliver_all).

    Returns:
        The scored run (check run["status"] == "passed", or use assert_run_passed).
    """
    created = client.create_run(
        project_id=project_id, mode="pull", scenarios=scenarios, time_scale=time_scale,
        trigger="ci" if os.environ.get("CI") else "api",
        commit_sha=os.environ.get("GITHUB_SHA"), branch=os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME"),
    )
    deliveries = created.get("deliveries", [])
    results = deliver_all(deliveries, target, **deliver_options)
    checks = _run_assertions(created.get("expectations", []), deliveries, results, assertions or {})
    return client.report_results(created["run"]["id"], results, checks)


def assert_run_passed(run: dict) -> None:
    """Raises AssertionError listing every failed check when a run didn't pass (pytest-friendly)."""
    if run.get("status") == "passed":
        return
    failed = [f"  ✗ {c['scenario']} · {c['name']}: {c['detail']}" for c in (run.get("results") or {}).get("checks", []) if not c["passed"]]
    raise AssertionError(f"MockCard run {run['id']} {run['status']} (score {run.get('score')}/100)\n" + "\n".join(failed) + f"\nDetails: https://www.mockcard.io/dashboard/runs/{run['id']}")
