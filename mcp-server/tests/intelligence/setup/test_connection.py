"""Provider-scoped connection tests never need application bootstrap."""

from __future__ import annotations

import unittest

from app.intelligence.credentials import CredentialStore, InMemoryCredentialBackend
from app.intelligence.registry.models.provider import AuthConfig, AuthType, ConnectionConfig, ProviderRecord
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType
from app.intelligence.setup.connection import ConnectionState, ProviderConnectionTester


class _ProbeAdapter:
    closed = False

    def __init__(self, record):
        self.record = record
        self.credential = None

    def attach_credential(self, credential):
        self.credential = credential

    def initialize(self):
        return None

    def validate_configuration(self):
        return None

    async def start(self):
        return None

    async def check_connection(self):
        return True

    async def close(self):
        self.closed = True


class ProviderConnectionTesterTests(unittest.TestCase):
    """The candidate lives only in the tester until persistence succeeds."""

    def test_candidate_probe_uses_only_selected_provider_and_closes_it(self):
        adapter = _ProbeAdapter(_record())
        tester = ProviderConnectionTester(factory=_Factory(adapter))

        result = tester.test(_record(), candidate_credential="candidate-secret")

        self.assertEqual(ConnectionState.READY, result.state)
        self.assertTrue(adapter.closed)
        self.assertEqual("candidate-secret", adapter.credential.api_key)


class _Factory:
    def __init__(self, adapter):
        self.adapter = adapter
        self.created = []

    def create(self, record):
        self.created.append(record.provider_id)
        return self.adapter


def _record() -> ProviderRecord:
    return ProviderRecord(
        provider_id="cloud",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(type=AuthType.API_KEY),
        connection=ConnectionConfig(base_url="https://example.invalid/v1"),
    )
