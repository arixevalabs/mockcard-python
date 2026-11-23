"""Tests for the Python SDK, using the shared conformance fixtures.

Author: Arixeva Labs <hello@arixevalabs.com>
"""
import json
from pathlib import Path

import pytest

from mockcard import assert_run_passed, deliver_all, verify_probe

FIXTURES = Path(__file__).resolve().parents[2] / "conformance"
PROBES = json.loads((FIXTURES / "probe-signatures.json").read_text())


@pytest.mark.parametrize("case", PROBES["cases"], ids=lambda c: c["name"])
def test_probe_verification_matches_conformance_vectors(case):
    assert verify_probe(case["headers"], case["body"], PROBES["secret"], now=PROBES["now"]) is case["valid"]
    meta = {"HTTP_" + k.upper().replace("-", "_"): v for k, v in case["headers"].items()}
    assert verify_probe(meta, case["body"].encode(), PROBES["secret"], now=PROBES["now"]) is case["valid"]


def test_deliver_all_batches_and_waits():
    deliveries = json.loads((FIXTURES / "pull-run.json").read_text())["deliveries"]
    sleeps, sent = [], []
    results = deliver_all(deliveries, "http://127.0.0.1/hook", sleep=sleeps.append, send=lambda t, d: (sent.append(d["id"]), {"delivery_id": d["id"], "status_code": 200, "duration_ms": 1})[1])
    assert sleeps == [1.8]
    assert sorted(sent[:2]) == ["dlv_1", "dlv_2"] and sent[2] == "dlv_3"
    assert [r["status_code"] for r in results] == [200, 200, 200]


def test_assert_run_passed_lists_failures():
    with pytest.raises(AssertionError, match="duplicate · fulfilled once: twice"):
        assert_run_passed({"id": "run_1", "status": "failed", "score": 50, "results": {"checks": [{"scenario": "duplicate", "name": "fulfilled once", "passed": False, "detail": "twice"}]}})
