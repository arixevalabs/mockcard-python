"""pytest plugin (auto-loaded when mockcard is installed): a ``mockcard`` fixture with a ready client.

    def test_webhooks_survive_chaos(mockcard):
        run = run_chaos(mockcard, "prj_…", "http://127.0.0.1:8000/webhooks/stripe/")
        assert_run_passed(run)

Author: Arixeva Labs <hello@arixevalabs.com>
"""
import os

import pytest

from .client import MockCard


@pytest.fixture
def mockcard() -> MockCard:
    """A MockCard client from MOCKCARD_API_KEY (and MOCKCARD_BASE_URL); skips the test when no key is set."""
    if not os.environ.get("MOCKCARD_API_KEY"):
        pytest.skip("MOCKCARD_API_KEY not set")
    return MockCard(base_url=os.environ.get("MOCKCARD_BASE_URL", "https://www.mockcard.io"))
