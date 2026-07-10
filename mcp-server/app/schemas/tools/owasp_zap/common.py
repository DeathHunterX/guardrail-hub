from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class OperationStatus(str, Enum):
    """Operation lifecycle.

    ``QUEUED`` operations are the persisted work queue itself (see the
    Operations table / DAO) — there is no separate in-memory waiting queue.
    A worker never has its own status; it only ever knows which
    ``operation_id`` (if any) it is currently executing.
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ZapScanMode(str, Enum):
    QUICK = "quick"
    FULL = "full"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ZapTokenType(str, Enum):
    BEARER = "bearer"
    JWT = "jwt"
    ACCESS_TOKEN = "access_token"
    CUSTOM = "custom"

class ScannerThreshold(str, Enum):
    DISABLE = "disable"
    DEFAULT = "default"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ZapApiTarget(BaseModel):
    url: str = Field(
        ...,
        description="Target API URL.",
        examples=["https://example.com/api/login"],
        alias="target_url",
    )

    method: HttpMethod = Field(
        ...,
        description="HTTP method used for request.",
        examples=[HttpMethod.POST],
    )

    headers: Optional[dict[str, str]] = Field(
        None,
        description="Additional HTTP headers.",
        examples=[{"Content-Type": "application/json"}],
    )

    body: Optional[Any] = Field(
        None,
        description="Request body. Can be JSON object, array, raw string, or form payload.",
    )

    token: Optional[str] = Field(
        None,
        description=(
            "Token value used for request authentication. "
            "Can represent Bearer token, JWT token, access token, or custom token."
        ),
    )

    token_type: ZapTokenType = Field(
        ZapTokenType.BEARER,
        description="Token type used to build authentication header.",
    )

    token_header_name: str = Field(
        "Authorization",
        description="Header name used to send token.",
    )

    token_prefix: Optional[str] = Field(
        None,
        description=(
            "Optional token prefix. "
            "If empty and token_type is bearer/jwt/access_token, backend can use 'Bearer'. "
            "For custom token, backend can use this prefix if provided."
        ),
        examples=["Bearer", "Token"],
    )

    cookie: Optional[str] = Field(
        None,
        description="Raw cookie string used to maintain session.",
    )

    token_field: Optional[str] = Field(
        None,
        description=(
            "Field path containing token in response, "
            "e.g. 'access_token', 'jwt', or 'data.access_token.token'."
        ),
        examples=["data.access_token.token"],
    )

    cookie_field: Optional[str] = Field(
        None,
        description="Field path containing cookie value in response.",
        examples=["data.cookie"],
    )

class ScannerThresholdOverride(BaseModel):
    rule_id: int = Field(
        ...,
        description="ZAP passive scanner rule ID. (e.g. 10038 for CSP violation)",
        examples=[10038],
    )
    threshold: ScannerThreshold = Field(
        ...,
        description="Alert threshold: disable, default, low, medium or high (default: default)",
        examples=[ScannerThreshold.DEFAULT],
    )
