"""The notification card's report link, for both tools' result shapes.

ZAP files its links under ``result["reports"]``, JMeter under
``result["artifacts"]`` — each is that tool's own wire format (ADR-0010), and
the resolver is the one place that has to read both. It previously read only
ZAP's key, so every JMeter notification rendered with no report link while the
whole ZAP suite stayed green.
"""

import unittest

from app.bootstrap import _operation_context_resolver
from app.constants.batch import BatchType
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase

_ZAP_LINK = "http://localhost:8787/public/report/owasp-zap/detail-report/op-1.html"
_JMETER_LINK = (
    "http://localhost:8787/public/report/jmeter/detail-report/op-1/report/index.html"
)


class _FakeDAO:
    def __init__(self, record):
        self._record = record

    def get_operation(self, _operation_id):
        return self._record


def _resolve(batch_type, result):
    record = OperationRecord(
        operation_id="op-1",
        status=OperationPhase.COMPLETED,
        batch_type=batch_type,
        metadata={"url": "https://api.example.com"},
        result=result,
    )
    return _operation_context_resolver(_FakeDAO(record))("op-1")


class ReportLinkResolutionTests(unittest.TestCase):
    def test_a_jmeter_result_yields_its_dashboard_link(self):
        context = _resolve(
            BatchType.JMETER_TEST, {"artifacts": {"view_report": _JMETER_LINK}}
        )
        self.assertEqual(_JMETER_LINK, context["report_link"])

    def test_a_zap_result_still_yields_its_report_link(self):
        context = _resolve(BatchType.API_SCAN, {"reports": {"view_report": _ZAP_LINK}})
        self.assertEqual(_ZAP_LINK, context["report_link"])

    def test_zap_wins_when_a_result_somehow_carries_both(self):
        context = _resolve(
            BatchType.API_SCAN,
            {"reports": {"view_report": _ZAP_LINK},
             "artifacts": {"view_report": _JMETER_LINK}},
        )
        self.assertEqual(_ZAP_LINK, context["report_link"])

    def test_each_tool_gets_its_own_card_title(self):
        self.assertEqual(
            "JMeter Load Test",
            _resolve(BatchType.JMETER_TEST, {"artifacts": {}})["title"],
        )
        self.assertEqual(
            "API Security Scan",
            _resolve(BatchType.API_SCAN, {"reports": {}})["title"],
        )

    def test_the_link_is_absolute_so_a_chat_client_can_open_it(self):
        # A Slack card is rendered far from the HTTP request that produced the
        # result; a server-relative "/public/..." there is unopenable.
        link = _resolve(
            BatchType.JMETER_TEST, {"artifacts": {"view_report": _JMETER_LINK}}
        )["report_link"]
        self.assertTrue(link.startswith("http://") or link.startswith("https://"), link)

    def test_a_result_without_links_resolves_to_none_not_an_error(self):
        self.assertIsNone(_resolve(BatchType.JMETER_TEST, None)["report_link"])
        self.assertIsNone(_resolve(BatchType.JMETER_TEST, {})["report_link"])
        self.assertIsNone(_resolve(BatchType.JMETER_TEST, {"artifacts": "x"})["report_link"])


if __name__ == "__main__":
    unittest.main()
