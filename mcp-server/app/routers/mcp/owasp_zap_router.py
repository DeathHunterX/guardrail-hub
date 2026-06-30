"""
OWASP ZAP MCP tools — exposed as FastAPI POST endpoints.

Each endpoint becomes an MCP tool via fastapi-mcp.
All blocking ZAP calls are offloaded to a thread pool with
``asyncio.to_thread`` so they do not block the event loop.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.tools.owasp_zap.api_scan import ZapApiScanLLMRequest
from app.services.tools.owasp_zap.api_scanner import ZapApiScanService

zap_router = APIRouter(prefix="/zap", tags=["OWASP ZAP"])


@zap_router.post("/scan_api", operation_id="zap_scan_api")
def zap_scan_api(request: ZapApiScanLLMRequest):
    """
    Run Owasp Zap scan

    Args:
        request: ZapApiScanLLMRequest
    Returns:

    """
    try:
        rs = ZapApiScanService().init_api_scan(request)
        return {"result": rs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running Owasp Zap scan: \n{str(e)}") from e
