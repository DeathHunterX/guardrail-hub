"""Authoritative credential-probe regressions for NVIDIA NIM."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.cli import main
from app.intelligence.credentials import CredentialStore, InMemoryCredentialBackend
from app.intelligence.providers.adapters import openai_compatible as openai_adapter_module
from app.intelligence.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from app.intelligence.providers.credential import ProviderCredential
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
from app.intelligence.registry.models.provider import AuthConfig, ConnectionConfig, ProviderRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


_PROBE_MODEL = "moonshotai/kimi-k3"
_CANDIDATE = "synthetic-invalid-nvidia-candidate"


class _ProbeHTTPError(Exception):
    pass


class _ProbeHeaders(dict):
    def get_list(self, name: str) -> list[str]:
        value = self.get(name)
        return [] if value is None else [value]


class _ProbeRequest:
    def __init__(self, method: str, path: str, headers: dict[str, str], payload=None) -> None:
        self.method = method
        self.url = type("URL", (), {"path": path})()
        self.headers = _ProbeHeaders(headers)
        self.content = b"" if payload is None else json.dumps(payload).encode("utf-8")


class _ProbeResponse:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise _ProbeHTTPError(f"synthetic HTTP {self.status_code}")

    def json(self):
        return self._payload


class _ProbeClient:
    def __init__(self, handler, **kwargs) -> None:
        self._handler = handler
        self._headers = dict(kwargs.get("headers", {}))

    async def get(self, path: str):
        return self._handler(_ProbeRequest("GET", path, self._headers))

    async def post(self, path: str, *, json=None):
        return self._handler(_ProbeRequest("POST", path, self._headers, json))

    async def aclose(self) -> None:
        return None


def _nvidia_record(*, auth_probe_model: str | None = _PROBE_MODEL) -> ProviderRecord:
    return ProviderRecord(
        provider_id="nvidia-nim",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(),
        connection=ConnectionConfig(
            base_url="https://integrate.api.nvidia.com/",
            auth_probe_model=auth_probe_model,
        ),
        capabilities=frozenset({Capability.CHAT}),
    )


async def _run_probe(handler, *, auth_probe_model: str | None = _PROBE_MODEL) -> bool:
    adapter = OpenAICompatibleAdapter(_nvidia_record(auth_probe_model=auth_probe_model))
    adapter.attach_credential(ProviderCredential(api_key=_CANDIDATE))
    adapter.initialize()
    client = _ProbeClient(
        handler,
        headers={"Authorization": f"Bearer {_CANDIDATE}"},
    )
    object.__setattr__(adapter, "_client", client)
    await adapter.start()
    try:
        with mock.patch.object(openai_adapter_module.httpx, "HTTPError", _ProbeHTTPError):
            return await adapter.check_connection()
    finally:
        await adapter.close()


class NvidiaAuthenticatedProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_anonymous_models_success_cannot_make_nvidia_ready(self) -> None:
        paths: list[str] = []

        def handler(request: _ProbeRequest) -> _ProbeResponse:
            paths.append(request.url.path)
            if request.url.path == "/v1/models":
                return _ProbeResponse(200)
            return _ProbeResponse(401)

        self.assertFalse(await _run_probe(handler))
        self.assertEqual(["/v1/chat/completions"], paths)

    async def test_authenticated_probe_rejects_401(self) -> None:
        self.assertFalse(await _run_probe(lambda _request: _ProbeResponse(401)))

    async def test_authenticated_probe_rejects_403(self) -> None:
        self.assertFalse(await _run_probe(lambda _request: _ProbeResponse(403)))

    async def test_authenticated_probe_rejects_malformed_and_unexpected_http_failures(self) -> None:
        for status in (400, 422, 500):
            with self.subTest(status=status):
                self.assertFalse(
                    await _run_probe(
                        lambda _request, status=status: _ProbeResponse(status)
                    )
                )

    async def test_authenticated_probe_rejects_transport_failure(self) -> None:
        def handler(_request: _ProbeRequest) -> _ProbeResponse:
            raise _ProbeHTTPError("synthetic transport failure")

        self.assertFalse(await _run_probe(handler))

    async def test_authenticated_probe_rejects_2xx_without_completion_result(self) -> None:
        self.assertFalse(await _run_probe(lambda _request: _ProbeResponse(200, {})))

    async def test_authenticated_probe_uses_minimal_valid_request_and_accepts_2xx(self) -> None:
        observed: dict[str, object] = {}

        def handler(request: _ProbeRequest) -> _ProbeResponse:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["authorization_count"] = len(request.headers.get_list("Authorization"))
            observed["authorization_is_bearer"] = (
                request.headers.get("Authorization") == f"Bearer {_CANDIDATE}"
            )
            observed["payload"] = json.loads(request.content)
            return _ProbeResponse(200, {"choices": [{"message": {"content": "pong"}}]})

        self.assertTrue(await _run_probe(handler))
        self.assertEqual("POST", observed["method"])
        self.assertEqual("/v1/chat/completions", observed["path"])
        self.assertEqual(1, observed["authorization_count"])
        self.assertTrue(observed["authorization_is_bearer"])
        self.assertEqual(
            {
                "model": _PROBE_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            },
            observed["payload"],
        )

    async def test_provider_without_auth_probe_model_keeps_models_probe(self) -> None:
        paths: list[str] = []

        def handler(request: _ProbeRequest) -> _ProbeResponse:
            paths.append(request.url.path)
            return _ProbeResponse(200, {"data": []})

        self.assertTrue(await _run_probe(handler, auth_probe_model=None))
        self.assertEqual(["/v1/models"], paths)


class AuthProbeMetadataTests(unittest.TestCase):
    def _load(self, auth_probe_model: str, *, strict: bool = False) -> tuple[object, ...]:
        content = f"""\
llm:
  providers:
    - id: nvidia-nim
      type: openai_compatible
      deployment: cloud
      auth: {{type: api_key, api_key_env: NVIDIA_API_KEY}}
      connection:
        base_url: https://integrate.api.nvidia.com/
        auth_probe_model: {auth_probe_model}
      models:
        - id: {_PROBE_MODEL}
          type: chat
          deployment_name: {_PROBE_MODEL}
          capabilities: [chat]
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "llm.yaml"
            path.write_text(content, encoding="utf-8")
            result = LLmConfigLoader().load(path, strict=strict)
        return result.providers, result.errors

    def test_loader_preserves_declared_non_secret_probe_model(self) -> None:
        providers, errors = self._load(_PROBE_MODEL)
        self.assertEqual([], errors)
        self.assertEqual(_PROBE_MODEL, providers[0].connection.auth_probe_model)

    def test_strict_loader_accepts_probe_metadata(self) -> None:
        providers, errors = self._load(_PROBE_MODEL, strict=True)
        self.assertEqual([], errors)
        self.assertEqual(_PROBE_MODEL, providers[0].connection.auth_probe_model)

    def test_loader_rejects_probe_model_not_declared_by_provider(self) -> None:
        providers, errors = self._load("unrelated/model")
        self.assertEqual([], providers)
        self.assertTrue(any("auth_probe_model" in str(error) for error in errors))


class _Output:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_line(self, text: str) -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class _SecretPrompt:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def read_secret(self, _label: str) -> str:
        return self.candidate


class NvidiaReconfigurePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Path(self.directory.name) / "llm.yaml"
        self.config.write_text(
            f"""\
llm:
  providers:
    - id: nvidia-nim
      type: openai_compatible
      deployment: cloud
      enabled: true
      auth: {{type: api_key, api_key_env: NVIDIA_API_KEY}}
      connection:
        base_url: https://integrate.api.nvidia.com/
        auth_probe_model: {_PROBE_MODEL}
      models:
        - id: {_PROBE_MODEL}
          type: chat
          deployment_name: {_PROBE_MODEL}
          capabilities: [chat]
""",
            encoding="utf-8",
        )
        self.store = CredentialStore(InMemoryCredentialBackend())
        self.environment = mock.patch.dict(
            os.environ, {"REGISTRY_LLM_CONFIG_PATH": str(self.config)}, clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def _client_factory(self, handler):
        def build(**kwargs):
            return _ProbeClient(handler, **kwargs)

        return build

    def test_invalid_replacement_preserves_existing_credential_byte_for_byte(self) -> None:
        existing = "synthetic-existing-credential"
        candidate = _CANDIDATE
        self.store.set("nvidia-nim", existing)
        output = _Output()

        def handler(request: _ProbeRequest) -> _ProbeResponse:
            if request.url.path == "/v1/models":
                return _ProbeResponse(200)
            return _ProbeResponse(401)

        with (
            mock.patch.object(
                openai_adapter_module.httpx,
                "AsyncClient",
                side_effect=self._client_factory(handler),
            ),
            mock.patch.object(openai_adapter_module.httpx, "HTTPError", _ProbeHTTPError),
        ):
            code = main(
                ["setup", "--provider", "nvidia-nim", "--reconfigure"],
                credential_store=self.store,
                secret_prompt=_SecretPrompt(candidate),
                output=output,
                input_reader=lambda _prompt, answers=iter(["3", "3"]): next(answers),
            )

        self.assertEqual(0, code)
        self.assertEqual(existing, self.store.get("nvidia-nim"))
        self.assertNotIn(candidate, output.text)
        self.assertIn("Existing credential was not changed.", output.text)

    def test_valid_replacement_persists_only_after_authenticated_probe(self) -> None:
        existing = "synthetic-existing-credential"
        replacement = "synthetic-valid-replacement"
        calls: list[str] = []
        credential_during_probe: list[str] = []
        authorization_was_single_bearer: list[bool] = []
        self.store.set("nvidia-nim", existing)
        output = _Output()

        def handler(request: _ProbeRequest) -> _ProbeResponse:
            calls.append(request.url.path)
            credential_during_probe.append(self.store.get("nvidia-nim"))
            authorization_was_single_bearer.append(
                len(request.headers.get_list("Authorization")) == 1
                and request.headers.get("Authorization") == f"Bearer {replacement}"
            )
            return _ProbeResponse(200, {"choices": [{"message": {"content": "pong"}}]})

        with (
            mock.patch.object(
                openai_adapter_module.httpx,
                "AsyncClient",
                side_effect=self._client_factory(handler),
            ),
            mock.patch.object(openai_adapter_module.httpx, "HTTPError", _ProbeHTTPError),
        ):
            code = main(
                ["setup", "--provider", "nvidia-nim", "--reconfigure"],
                credential_store=self.store,
                secret_prompt=_SecretPrompt(replacement),
                output=output,
                input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
            )

        self.assertEqual(0, code)
        self.assertEqual(["/v1/chat/completions"], calls)
        self.assertEqual([existing], credential_during_probe)
        self.assertEqual([True], authorization_was_single_bearer)
        self.assertEqual(replacement, self.store.get("nvidia-nim"))
        self.assertNotIn(replacement, output.text)
        self.assertIn("Credential updated securely", output.text)


if __name__ == "__main__":
    unittest.main()
