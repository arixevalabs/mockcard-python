# mockcard (Python)

Payment failure testing for Python. Run MockCard's chaos scenarios against your webhook handler in CI,
assert what your app did, and guard production against MockCard's monitoring probes. Standard library
only; includes a pytest plugin.

Author: Arixeva Labs <hello@arixevalabs.com> · [mockcard.io](https://www.mockcard.io) · MIT

```sh
pip install mockcard
```

## Chaos run in pytest

```python
from mockcard import run_chaos, assert_run_passed

def test_webhooks_survive_chaos(mockcard, live_server):  # `mockcard` fixture comes with the package
    run = run_chaos(
        mockcard, "prj_…", f"{live_server.url}/webhooks/stripe/",
        scenarios=["success", "duplicate", "latency", "3ds_abandoned", "limbo"],
        assertions={"duplicate": {"order fulfilled once": lambda ctx: Order.objects.filter(status="paid").count() == 1}},
    )
    assert_run_passed(run)
```

The fixture reads `MOCKCARD_API_KEY` and skips the test when it isn't set.

## Production probe guard

Django:

```python
from django.http import JsonResponse
from mockcard import is_probe, verify_probe, PROBE_ACK_HEADER

def stripe_webhook(request):
    if is_probe(request.META) and verify_probe(request.META, request.body, settings.MOCKCARD_PROBE_SECRET):
        return JsonResponse({"probe": True}, headers={PROBE_ACK_HEADER: "skipped"})
    ...  # normal handling
```

FastAPI:

```python
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    if is_probe(request.headers) and verify_probe(request.headers, body, PROBE_SECRET):
        return JSONResponse({"probe": True}, headers={PROBE_ACK_HEADER: "skipped"})
    ...
```

API reference: https://www.mockcard.io/openapi.yaml
