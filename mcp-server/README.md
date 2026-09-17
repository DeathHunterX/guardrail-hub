# Guardrail Hub MCP Server

## LLM operator CLI

`llm.yaml` declares provider/model topology and never contains a credential
value. The CLI separates topology changes from provider operation:

```text
guardrail-hub
├── setup [--provider PROVIDER_ID] [--credential | --reconfigure]
└── config
    ├── show
    ├── validate LLM_YAML
    └── apply LLM_YAML
```

`setup` works on providers already present in the canonical `config/llm.yaml`.
It presents a readiness dashboard, then lets an operator reconfigure an
existing stored credential, add a missing credential, or test a selected
provider. It never adds providers or models. Use `config apply` for every
provider/model topology, routing, priority, or enabled-state change.

Credentials are requested only through hidden input. They are never accepted
as command-line arguments, written to `llm.yaml`, or written to `.env` files.
A new credential is tested against the selected provider before it is stored.
During reconfiguration the old credential remains authoritative until the new
candidate succeeds.

### Config commands

```powershell
guardrail-hub config show
guardrail-hub config validate .\candidate-llm.yaml
guardrail-hub config apply .\candidate-llm.yaml
```

`show` renders only provider/model metadata. `validate` reads a candidate,
rejects unknown keys and literal `auth.api_key`, then runs the same catalog and
registry validation used by runtime. It does not read credentials or contact
providers. `apply` is interactive: it validates the exact bytes once, shows a
semantic provider/model diff, asks for confirmation, and atomically replaces
the canonical file. It fails closed without an interactive terminal.

### Setup examples

```powershell
guardrail-hub setup
guardrail-hub setup --provider nvidia-nim
guardrail-hub setup --provider nvidia-nim --credential
guardrail-hub setup --provider nvidia-nim --reconfigure
```

For the supported Linux Docker Compose host flow, run the checkout-local CLI
from the repository root as follows:

```bash
cd mcp-server
uv run guardrail-hub setup
uv run guardrail-hub setup --provider nvidia-nim
uv run guardrail-hub setup --provider nvidia-nim --credential
uv run guardrail-hub setup --provider nvidia-nim --reconfigure
```

The `mcp-server` working directory matters: it lets setup anchor
`config/llm.yaml`, verify this project's read-only Compose secret mount, and
provision the host file at `secrets/<provider_id>`. Generic Linux directories
remain read-only or fail closed; setup never guesses a writable secret root.

An unknown provider is intentionally not created by setup. Apply a revised
configuration first:

```text
guardrail-hub config apply <llm.yaml>
```

## Credential deployment

Provider credentials are keyed by provider ID. `auth.api_key_env` is locator
metadata for explicit environment mode, never a credential value.

| Context | Setup behaviour | Credential storage |
| --- | --- | --- |
| Windows local | Auto-detects local context | Windows Credential Manager `GuardrailHub:<provider_id>` |
| Recognized Compose host | Auto-detects only the trusted project layout | Protected host `secrets/<provider_id>` file |
| Windows Compose ambiguity | Asks interactively which deployment context is being configured; noninteractive use fails closed | Chosen secure mechanism |
| MCP container / file mount | Read-only dashboard and testing context | Externally provisioned file |
| Explicit `env` backend / generic external deployment | Read-only dashboard and testing context | Externally managed environment |

The Compose host provisioner recognizes only the checked-out Guardrail Hub
Compose layout. It creates protected host secret files and the container mounts
them read-only at `/run/secrets/<provider_id>`. A container never writes that
mount. Generic Linux never guesses a writable secret location.

Set `GUARDRAILHUB_CREDENTIAL_BACKEND=file` for a deliberately file-mounted
deployment, or `GUARDRAILHUB_CREDENTIAL_BACKEND=env` for an explicitly
environment-managed deployment. Both remain read-only. In either context,
setup explains that the deployment owner must supply missing credentials; it
does not make `/run/secrets/<provider_id>` its primary operator instruction.

Windows Credential Manager, Compose host file permissions/ACLs, atomic secret
replacement, path traversal/reparse protection, and AWS credential-chain
isolation remain runtime security invariants. AWS providers use the AWS SDK
credential chain and do not use API-key storage.

### Troubleshooting without exposing secrets

The setup dashboard distinguishes credential state from connection state.
Credential presence is not proof of connectivity. A probe reports only a safe
outcome; it does not include raw provider exception text. Do not paste a key
into command arguments, `llm.yaml`, an environment file, or diagnostic output.
