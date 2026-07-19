"""Pure helpers to derive an executive view from aggregated child findings.

No ZAP / IO dependency — turns raw child alerts + severity counts into the
report's higher-level sections (overall risk, deduplicated detailed findings,
and actionable recommendations) so Markdown / JSON / SARIF all describe the same
thing.
"""

from typing import Any

# Highest → lowest. Index used both for ranking and for "overall risk".
RISK_ORDER = ["High", "Medium", "Low", "Informational"]
_RISK_RANK = {name.lower(): i for i, name in enumerate(RISK_ORDER)}

# Generic, human-readable guidance per severity present in the results.
_SEVERITY_ADVICE = {
    "high": (
        "Address High-risk findings before release — these are exploitable "
        "vulnerabilities (e.g. injection, broken auth)."
    ),
    "medium": (
        "Plan remediation for Medium-risk findings; they often become exploitable "
        "when combined with other weaknesses."
    ),
    "low": "Review Low-risk findings and fix where inexpensive; track the rest.",
    "informational": (
        "Informational items are hardening opportunities (headers, disclosure); "
        "adopt them as time allows."
    ),
}


def risk_rank(risk: str) -> int:
    """Return a sort rank for a risk label (0 = most severe)."""
    return _RISK_RANK.get(str(risk).lower(), len(RISK_ORDER))


def overall_risk(severity_summary: dict) -> str:
    """Return the highest severity present, or ``"None"`` when there are no findings."""
    for name in RISK_ORDER:
        if severity_summary.get(name.lower(), 0):
            return name
    return "None"


def collect_findings(outcomes: list) -> list[dict]:
    """Deduplicate child alerts into ranked detailed findings.

    Alerts are grouped by ``(rule_id, name, risk)``; instances are counted and
    the affected categories/URLs recorded. Sorted by severity, then by count.
    """
    grouped: dict[tuple, dict] = {}
    for outcome in outcomes:
        for alert in outcome.alerts:
            rule_id = str(alert.get("alert_ref") or alert.get("name") or "zap")
            name = alert.get("name", rule_id)
            risk = alert.get("risk", "Informational")
            key = (rule_id, name, risk)
            entry = grouped.setdefault(
                key,
                {
                    "rule_id": rule_id,
                    "name": name,
                    "risk": risk,
                    "count": 0,
                    "categories": set(),
                    "example_url": alert.get("url") or outcome.url,
                    "solution": alert.get("solution") or "",
                },
            )
            entry["count"] += 1
            entry["categories"].add(outcome.category)

    findings = []
    for entry in grouped.values():
        entry["categories"] = sorted(entry["categories"])
        findings.append(entry)
    findings.sort(key=lambda f: (risk_rank(f["risk"]), -f["count"]))
    return findings


def derive_recommendations(findings: list[dict], severity_summary: dict) -> list[str]:
    """Build a short, prioritized list of recommendations."""
    if not findings:
        return ["No findings — no action required. Re-scan after significant changes."]

    recommendations: list[str] = []
    for severity in ("high", "medium", "low", "informational"):
        if severity_summary.get(severity, 0):
            recommendations.append(_SEVERITY_ADVICE[severity])

    # Call out the single most impactful finding by name.
    top = findings[0]
    recommendations.append(
        f"Start with '{top['name']}' ({top['risk']}), seen {top['count']} time(s) "
        f"in {', '.join(top['categories'])}."
    )
    return recommendations


def executive_summary(
    suite_name: str, application_summary: dict, findings: list[dict]
) -> dict[str, Any]:
    """Build the executive summary block (posture at a glance)."""
    risk = overall_risk(application_summary)
    total = application_summary.get("total", 0)
    if total == 0:
        headline = f"No security findings across {application_summary.get('endpoints', 0)} endpoint(s)."
    else:
        headline = (
            f"{application_summary.get('high', 0)} High / "
            f"{application_summary.get('medium', 0)} Medium finding(s) across "
            f"{application_summary.get('endpoints', 0)} endpoint(s) — overall risk: {risk}."
        )
    return {
        "suite_name": suite_name,
        "overall_risk": risk,
        "endpoints_scanned": application_summary.get("endpoints", 0),
        "endpoints_failed": application_summary.get("failed", 0),
        "total_findings": total,
        "distinct_findings": len(findings),
        "headline": headline,
    }
