"""Shared fixtures for Workato Connector PST (Plausible Scenario Testing).

Mirrors the accepted pattern used by n8n Connector / DataForSEO Connector:
imperal_sdk.testing.MockContext + MockSecretStore give us the REAL
handlers.py / workato_client.py code path (real HTTP call construction,
real header names, real error mapping) against a controlled fake HTTP
backend -- not a hand-rolled imitation of the logic itself.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def ctx():
    from imperal_sdk.testing import MockContext, MockSecretStore

    mock = MockContext()
    mock.secrets = MockSecretStore({})
    return mock


@pytest.fixture
def ctx_connected(ctx):
    """Same as `ctx` but with Workato credentials already saved -- the
    state every persona in SCENARIO_TESTS.md starts from except the
    brand-new user in the connection scenarios."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "workato_api_token": "wrkt_api_test_token_5f3a9c",
        "workato_data_center": "www.workato.com",
    })
    return ctx
