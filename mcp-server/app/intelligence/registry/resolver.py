"""Environment-variable resolver for the registry YAML.

The registry is a deployment artifact. A real production deployment MUST NOT
contain secrets in the YAML file — secrets live in the environment or in a
secret manager. The resolver substitutes ``${ENV_VAR}`` placeholders inside
strings (recursively, including inside lists and dicts) so the registry can
reference env values without holding them.

Contract:

- A string ``"${ENV_VAR}"`` resolves to the value of ``os.environ["ENV_VAR"]``.
- A string ``"prefix-${ENV_VAR}-suffix"`` resolves to the literal value with
  the placeholder substituted.
- An unset env var produces a :class:`LoadIssue` (the caller decides whether
  it is fatal).
- Recursion is bounded; non-string scalars (int, bool, float, None) are
  returned unchanged.

Authority: Decision 0014 §3 — the registry does not interpret credentials,
it only parses them. Resolution happens at the loader boundary, not inside
the records.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

# Pattern matches ${NAME} where NAME is a non-empty sequence of
# word characters, dots, and underscores. The braces are required so
# that a literal '$' in a YAML value is not misinterpreted.
_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.]*)\}")


@dataclass(frozen=True, slots=True)
class ResolvedString:
    """A string after env-variable resolution.

    The original (with placeholders) is preserved on ``raw`` for diagnostics;
    ``value`` is the substituted form.
    """

    value: str
    raw: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class EnvironmentResolver:
    """Substitutes ``${ENV_VAR}`` placeholders with ``os.environ`` values.

    Stateless after construction. ``resolve`` may be called any number of
    times. The resolver takes the environment as a keyword argument so tests
    can inject a fixed mapping without touching the real environment.
    """

    DEFAULT_PATTERN = _PATTERN

    def __init__(self, pattern: re.Pattern[str] | None = None) -> None:
        self._pattern = pattern or self.DEFAULT_PATTERN

    def resolve_string(
        self,
        value: str,
        *,
        env: Mapping[str, str] | None = None,
    ) -> tuple[str, list[str]]:
        """Resolve a single string.

        Args:
            value: The string to resolve.
            env: Optional environment mapping (defaults to ``os.environ``).

        Returns:
            Tuple of (resolved_string, list_of_unresolved_names). The list is
            empty when every placeholder resolves; otherwise it contains each
            unresolved env-var name in order of appearance.
        """
        environment = os.environ if env is None else env
        unresolved: list[str] = []

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in environment:
                return str(environment[name])
            if name not in unresolved:
                unresolved.append(name)
            return match.group(0)  # leave unresolved placeholders intact

        resolved = self._pattern.sub(replace, value)
        return resolved, unresolved

    def resolve(
        self,
        data: Any,
        *,
        env: Mapping[str, str] | None = None,
    ) -> tuple[Any, list[tuple[str, str]]]:
        """Recursively resolve placeholders in ``data``.

        Strings are processed. Dicts, lists, and tuples are recursed into.
        All other scalars (int, bool, float, None) pass through unchanged.

        Args:
            data: Arbitrary parsed YAML data.
            env: Optional environment mapping (defaults to ``os.environ``).

        Returns:
            Tuple of (resolved_data, list_of_(position, env_var_name) for
            each unresolved placeholder). ``position`` is a dotted path
            (e.g. ``providers[0].auth.api_key_env``) suitable for diagnostics.
        """
        environment = os.environ if env is None else env
        unresolved: list[tuple[str, str]] = []
        resolved = self._recurse(data, path=(), env=environment, unresolved=unresolved)
        return resolved, unresolved

    def _recurse(
        self,
        data: Any,
        *,
        path: tuple[Any, ...],
        env: Mapping[str, str],
        unresolved: list[tuple[str, str]],
    ) -> Any:
        if isinstance(data, str):
            value, names = self.resolve_string(data, env=env)
            for name in names:
                unresolved.append((_format_path(path), name))
            return value
        if isinstance(data, dict):
            return {
                key: self._recurse(
                    value, path=path + (key,), env=env, unresolved=unresolved
                )
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [
                self._recurse(
                    item, path=path + (f"[{i}]",), env=env, unresolved=unresolved
                )
                for i, item in enumerate(data)
            ]
        return data


def _format_path(parts: tuple[Any, ...]) -> str:
    """Render a structured path as a diagnostic string.

    Examples:
        () -> "(root)"
        ("providers",) -> "providers"
        ("providers", "[0]", "auth", "api_key_env") -> "providers[0].auth.api_key_env"
    """
    if not parts:
        return "(root)"
    out = []
    for i, part in enumerate(parts):
        if isinstance(part, str) and part.startswith("[") and part.endswith("]"):
            out.append(part)
        elif i == 0:
            out.append(str(part))
        else:
            out.append(f".{part}")
    return "".join(out)


__all__ = [
    "EnvironmentResolver",
    "ResolvedString",
]
