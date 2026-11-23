"""Production probe guard.

MockCard monitors send probes with ``MockCard-Probe: 1`` and
``MockCard-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">`` under your project's probe
secret. Verify, skip all processing, and answer 2xx with ``MockCard-Probe-Ack: skipped``. A forged
probe header can only make your handler skip, never process.

Author: Arixeva Labs <hello@arixevalabs.com>
"""
from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Mapping, Optional

PROBE_ACK_HEADER = "MockCard-Probe-Ack"
_TOLERANCE_SECONDS = 300
_SIGNATURE = re.compile(r"^t=(\d+),v1=([0-9a-f]{64})$")


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    """Reads a header case-insensitively; also accepts WSGI-style HTTP_* keys (Django's request.META)."""
    wsgi = "http_" + name.replace("-", "_")
    for key, value in headers.items():
        if key.lower() in (name, wsgi):
            return value
    return None


def is_probe(headers: Mapping[str, str]) -> bool:
    """Whether a request claims to be a MockCard probe (verify before trusting it)."""
    return _header(headers, "mockcard-probe") == "1"


def verify_probe(headers: Mapping[str, str], raw_body: bytes | str, probe_secret: str, now: Optional[int] = None) -> bool:
    """Verifies a probe's signature and age.

    Args:
        headers: Request headers (any case, or WSGI environ / request.META).
        raw_body: The exact request body.
        probe_secret: Your project's probe secret.
        now: Current Unix time (injectable for tests).

    Returns:
        True for a genuine, recent MockCard probe.
    """
    if not probe_secret or not is_probe(headers):
        return False
    match = _SIGNATURE.match(_header(headers, "mockcard-signature") or "")
    if not match:
        return False
    timestamp, given = match.groups()
    if abs((now if now is not None else int(time.time())) - int(timestamp)) > _TOLERANCE_SECONDS:
        return False
    body = raw_body.decode() if isinstance(raw_body, bytes) else raw_body
    expected = hmac.new(probe_secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)
