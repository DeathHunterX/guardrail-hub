"""
Filesystem path constants for generated artifacts.

All paths are relative to the project root and must remain stable across
deployments — they are referenced by both application code and Docker volume
mounts (docker-compose.yml).  Do not make these configurable.

Public URL layout (served at /public/**):
  /public/report/owasp-zap/detail-report/{op_id}       → HTML report
  /public/report/owasp-zap/detail-report/{op_id}.json  → JSON report
  /public/s3-management/                                → future
"""


class ReportPaths:
    BASE_DIR = "./public"
    ZAP_DETAIL_DIR = "./public/report/owasp-zap/detail-report"
