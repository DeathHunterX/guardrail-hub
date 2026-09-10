# Guardrail Hub MCP Server

## LLM configuration commands

Use the CLI to inspect and manage provider/model topology in `config/llm.yaml`:

```powershell
guardrail-hub config show
guardrail-hub config validate .\candidate-llm.yaml
guardrail-hub config apply .\candidate-llm.yaml
```

`show` renders provider and model metadata without reading credentials. `validate` strictly rejects unsupported fields and literal `auth.api_key` values without changing the canonical file. `apply` validates the candidate bytes, shows a semantic change summary, asks for confirmation, and atomically replaces the canonical file. It requires an interactive terminal.

## LLM credential deployment

LLM provider configuration lives in `config/llm.yaml`. It identifies a provider
and its authentication method; it never contains a credential value. For an
API-key provider, the credential identity is always the provider ID. For
example, the configured `openai-cloud` provider is looked up as
`openai-cloud`.

Select the credential backend at startup with
`GUARDRAILHUB_CREDENTIAL_BACKEND`:

| Deployment | Selector | Where the API-key provider credential is read |
| --- | --- | --- |
| Windows development | `windows` | Windows Credential Manager target `GuardrailHub:<provider_id>` |
| Container or other non-Windows file-mounted deployment | `file` | `<secrets_dir>/<provider_id>` |
| Explicit environment-variable deployment | `env` | The provider's configured `auth.api_key_env`, or its fallback name |

On non-Windows hosts, the selector must be explicitly set to `file` or `env`.
An unset, unsupported, or platform-incompatible selection prevents startup; the
server does not choose a fallback backend automatically.

### Windows development

Set `GUARDRAILHUB_CREDENTIAL_BACKEND=windows`. Provision each API-key
credential in Windows Credential Manager using its provider ID. For example,
the `openai-cloud` provider uses the target `GuardrailHub:openai-cloud`.

`auth.api_key_env` does not change the Windows Credential Manager target.

### Containers and file-mounted secrets

Set `GUARDRAILHUB_CREDENTIAL_BACKEND=file`. The default secrets directory is
`/run/secrets`, so the credential for `openai-cloud` is read from
`/run/secrets/openai-cloud`.

Set `GUARDRAILHUB_SECRETS_DIR` only when the deployment mounts secrets in a
different directory. The resulting path is always
`<secrets_dir>/<provider_id>`; `auth.api_key_env` is not a filename and has no
effect in file mode. Provision the secret through the deployment platform and
keep any local `secrets/` directory out of version control.

### Linux Docker Compose host provisioning

For the supported Linux Compose host flow, run setup from the project checkout:

```bash
cd mcp-server
uv run guardrail-hub setup --provider nvidia-nim
```

`cd mcp-server` is currently required because setup anchors `config/llm.yaml`
there before it recognizes the approved Compose project and its host
`secrets/<provider_id>` target. This makes the host provisioning context
writable. The running MCP container instead reads the corresponding
`/run/secrets/<provider_id>` mount through its read-only file backend; it does
not write credentials.

### Explicit environment-variable mode

Environment-variable credentials are an explicit opt-in. Set
`GUARDRAILHUB_CREDENTIAL_BACKEND=env` only for deployments that intentionally
provide credentials through the process environment.

In this mode, `auth.api_key_env` is the physical environment-variable mapping.
For a provider with `provider_id: openai-cloud` and
`api_key_env: OPENAI_API_KEY`, the logical lookup remains `openai-cloud`, while
the environment backend reads `OPENAI_API_KEY`.

If an API-key provider has no `api_key_env`, the environment backend uses the
exact fallback `GUARDRAILHUB_CREDENTIAL__{provider_id.upper()}`. For
`openai-cloud`, that is `GUARDRAILHUB_CREDENTIAL__OPENAI-CLOUD`; provider IDs
are not normalized.

Do not put provider credential values in `.env.example`, `llm.yaml`, logs, or
command output. Environment mode can expose values more broadly to processes
and deployment tooling than a file-mounted secret, so use file mode for
container deployments where it is available.

### AWS Bedrock

Providers configured with `auth.type: aws`, including Bedrock, use the AWS SDK
credential provider chain. They do not use Guardrail Hub's API-key credential
storage or `GUARDRAILHUB_CREDENTIAL_BACKEND` for AWS authentication.

### Troubleshooting without exposing secrets

If startup reports that no credential backend is available, set a supported
backend selector appropriate for the host. For file mode, confirm that the
configured directory is mounted and contains a readable secret file named for
the provider ID. For environment mode, confirm that the mapped environment
variable exists and is non-empty. A missing provider credential is reported by
provider ID; do not print or paste the credential value while diagnosing it.
