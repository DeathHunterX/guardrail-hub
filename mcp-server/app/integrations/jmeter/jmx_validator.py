"""JMX whitelist validation — treat an uploaded plan as an executable document.

A JMeter ``.jmx`` file is not data; it is a program JMeter will execute. So it is
validated *before* it is stored or handed to any worker (ADR-0010 §5 S1 / INV3),
against an **allow-list** of safe JMeter components. Two rejections are possible:

1. **Scripting / native execution** — BeanShell, JSR223 (any language), Java
   Sampler, and OS Process (``SystemSampler``) elements are refused explicitly,
   with a security-specific message. These are the elements that turn a load
   test into arbitrary code execution.
2. **Unknown component** — any component not on the allow-list is refused by
   default (whitelist, not blacklist). We control plan generation, so the safe
   set is knowable; anything outside it fails closed.

Parsing itself is hardened: the document is untrusted, so it is parsed with
``defusedxml`` (entity-expansion bombs and external-entity/XXE attacks are
rejected at parse time, before any element walk).

Only elements that carry a ``testclass`` or ``elementType`` attribute — i.e.
actual JMeter components/config, not the deep property serialization
(``stringProp``, ``objProp`` value fields, …) — are validated. This is why a
normal plan's save-configuration fields do not trip the whitelist.
"""

from __future__ import annotations

from typing import Iterable, List

from defusedxml.ElementTree import fromstring


class JmxValidationError(ValueError):
    """Raised when a JMX plan is not safe to execute (or not a JMeter plan)."""


# Scripting / native-execution families. Matched as a substring of a component's
# tag / testclass / elementType (case-insensitive, whitespace removed) so every
# variant is caught — e.g. JSR223Sampler, JSR223PreProcessor, JSR223Assertion,
# BeanShellSampler, BeanShellPostProcessor, JavaSampler, SystemSampler.
_FORBIDDEN_SUBSTRINGS = ("beanshell", "jsr223", "javasampler", "systemsampler")

# Allow-list of safe JMeter component / config types. Deliberately conservative:
# HTTP performance testing plus the structural/config/timer/assertion/extractor
# elements our generated plans use. A genuinely new safe component is added here
# explicitly — never inferred.
_ALLOWED_COMPONENTS = frozenset(
    {
        # Plan & thread groups
        "TestPlan", "ThreadGroup", "SetupThreadGroup", "PostThreadGroup",
        # Controllers
        "LoopController", "GenericController", "TransactionController",
        "OnceOnlyController", "IfController", "WhileController",
        "ForeachController", "RunTime", "InterleaveControl", "RandomController",
        "RandomOrderController", "ThroughputController",
        "CriticalSectionController", "ModuleController",
        # Samplers (safe — no scripting / no native process)
        "HTTPSamplerProxy", "DebugSampler", "TestAction",
        # Config / data
        "ConfigTestElement", "Arguments", "Argument", "HTTPArgument",
        "HeaderManager", "CookieManager", "CacheManager", "DNSCacheManager",
        "AuthManager", "Authorization", "CSVDataSet", "LoginConfig",
        "RandomVariableConfig", "CounterConfig", "KeystoreConfig",
        # Timers (non-scripted)
        "ConstantTimer", "UniformRandomTimer", "GaussianRandomTimer",
        "ConstantThroughputTimer", "PoissonRandomTimer", "SyncTimer",
        "PreciseThroughputTimer",
        # Assertions (non-scripted)
        "ResponseAssertion", "JSONPathAssertion", "JMESPathAssertion",
        "DurationAssertion", "SizeAssertion", "XPathAssertion",
        "XPath2Assertion", "MD5HexAssertion", "HTMLAssertion", "SMIMEAssertion",
        "CompareAssertion",
        # Pre/Post processors (non-scripted extractors)
        "RegexExtractor", "XPathExtractor", "XPath2Extractor",
        "JSONPostProcessor", "JMESPathExtractor", "BoundaryExtractor",
        "HtmlExtractor", "DebugPostProcessor",
        # Listeners
        "ResultCollector",
    }
)

_ROOT_TAG = "jmeterTestPlan"


def validate_jmx(content: str | bytes) -> None:
    """Validate a JMX plan; raise :class:`JmxValidationError` if unsafe.

    Returns ``None`` on success. Raises on: a non-JMeter or malformed document,
    a hardened-parse rejection (entity bomb / external entity), any scripting /
    native-execution component, or any component not on the allow-list.
    """
    try:
        root = fromstring(content)
    except JmxValidationError:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        # Covers ParseError plus defusedxml's EntitiesForbidden / DTDForbidden /
        # ExternalReferenceForbidden — an untrusted document that will not parse
        # safely is not a valid plan.
        raise JmxValidationError(f"Plan is not parseable as safe XML: {exc}") from exc

    tag = _localname(root.tag)
    if tag != _ROOT_TAG:
        raise JmxValidationError(
            f"Not a JMeter test plan (root element is '{tag}', expected '{_ROOT_TAG}')."
        )

    forbidden: List[str] = []
    unknown: List[str] = []
    for element in root.iter():
        component = _component_type(element)
        if component is None:
            continue  # property leaf / serialization detail — not a component
        if _is_forbidden(component) or _is_forbidden(_localname(element.tag)):
            forbidden.append(component)
        elif component not in _ALLOWED_COMPONENTS:
            unknown.append(component)

    if forbidden:
        raise JmxValidationError(
            "Plan contains scripting / native-execution elements, which are not "
            f"permitted: {_summarize(forbidden)}."
        )
    if unknown:
        raise JmxValidationError(
            "Plan contains components that are not on the safe allow-list "
            f"(rejected by default): {_summarize(unknown)}."
        )


def _component_type(element) -> str | None:
    """The JMeter component/config type an element declares, or None.

    JMeter marks components with ``testclass`` and nested config with
    ``elementType``; everything else (``stringProp``, ``objProp`` value fields)
    is serialization and carries neither.
    """
    return element.get("testclass") or element.get("elementType")


def _is_forbidden(name: str) -> bool:
    normalized = name.lower().replace(" ", "")
    return any(bad in normalized for bad in _FORBIDDEN_SUBSTRINGS)


def _localname(tag: str) -> str:
    """Strip any XML namespace prefix (``{ns}Tag`` -> ``Tag``)."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _summarize(names: Iterable[str]) -> str:
    """Deduplicated, order-stable, comma-joined list for error messages."""
    seen: List[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return ", ".join(seen)
