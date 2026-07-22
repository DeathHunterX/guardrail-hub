"""Unit tests for artifact redaction (ADR-0010 §5 S4 / INV4 / INV10)."""

import tempfile
import unittest
from pathlib import Path

from app.services.performance.engine.dto import Artifact, ArtifactKind, ArtifactSet
from app.services.performance.redaction import (
    redact_artifacts,
    redact_file,
    redact_text,
)

_SECRET = "s3cr3t-value-should-never-persist"


class RedactHeadersTests(unittest.TestCase):
    def test_every_sensitive_header_value_is_redacted(self):
        for header in (
            "Authorization",
            "Proxy-Authorization",
            "Cookie",
            "Set-Cookie",
            "X-API-Key",
            "X-Amz-Security-Token",
        ):
            line = f"{header}: {_SECRET}"
            out = redact_text(line)
            self.assertNotIn(_SECRET, out, f"{header} value survived redaction")
            self.assertIn(f"{header}:", out, f"{header} name should be preserved")
            self.assertIn("[REDACTED]", out)

    def test_header_matching_is_case_insensitive(self):
        out = redact_text(f"authorization: Bearer {_SECRET}")
        self.assertNotIn(_SECRET, out)

    def test_redaction_is_line_scoped(self):
        text = f"Authorization: {_SECRET}\nUser-Agent: keep-me/1.0"
        out = redact_text(text)
        self.assertNotIn(_SECRET, out)
        self.assertIn("keep-me/1.0", out)  # non-sensitive lines untouched

    def test_non_sensitive_text_is_unchanged(self):
        text = "GET /health\nStatus: 200\nDuration: 12ms"
        self.assertEqual(redact_text(text), text)


class RedactTokenPatternsTests(unittest.TestCase):
    def test_jwt_anywhere_is_redacted(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc-DEF_123"
        out = redact_text(f"url=/cb?token={jwt}&x=1")
        self.assertNotIn(jwt, out)
        self.assertIn("[REDACTED_JWT]", out)

    def test_basic_credentials_are_redacted(self):
        out = redact_text("Authorization: Basic dXNlcjpwYXNzd29yZA==")
        self.assertNotIn("dXNlcjpwYXNzd29yZA==", out)


class RedactFileAndArtifactsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_redact_file_rewrites_in_place(self):
        f = self.dir / "results.jtl"
        f.write_text(f"Cookie: session={_SECRET}\n")
        redact_file(f)
        self.assertNotIn(_SECRET, f.read_text())

    def test_redact_file_ignores_binary(self):
        f = self.dir / "blob.bin"
        f.write_bytes(b"\xff\xfe\x00\x01not-utf8")
        redact_file(f)  # must not raise
        self.assertEqual(f.read_bytes(), b"\xff\xfe\x00\x01not-utf8")

    def test_redact_artifacts_covers_files_and_report_dir(self):
        # Realistic artifact content: headers appear as their own "Name: value"
        # lines (as JMeter stores them in JTL/logs); a JWT can appear embedded
        # anywhere and is caught by the token pattern during the directory walk.
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig-value_123"
        results = self.dir / "results.jtl"
        results.write_text(f"Set-Cookie: id={_SECRET}\nContent-Type: text/html\n")
        report = self.dir / "report"
        (report / "content").mkdir(parents=True)
        (report / "detail.log").write_text(f"Authorization: Bearer {_SECRET}\n")
        (report / "content" / "trace.txt").write_text(f"redirect to /cb?token={jwt}\n")

        redact_artifacts(
            ArtifactSet(
                (
                    Artifact(ArtifactKind.RESULTS, results),
                    Artifact(ArtifactKind.REPORT, report),
                )
            )
        )

        self.assertNotIn(_SECRET, results.read_text())
        self.assertIn("text/html", results.read_text())  # non-secret line kept
        self.assertNotIn(_SECRET, (report / "detail.log").read_text())
        self.assertNotIn(jwt, (report / "content" / "trace.txt").read_text())


if __name__ == "__main__":
    unittest.main()
