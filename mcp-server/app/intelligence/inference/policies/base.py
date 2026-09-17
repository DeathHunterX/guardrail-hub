"""Inference Policy base — interface for request/response policies.

Policies handle cross-cutting concerns like:
- Request validation
- Response transformation
- Rate limiting
- Caching
- Metrics
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class InferencePolicy(ABC):
    """Base class for inference policies.

    Policies are middleware-like components that can intercept
    and modify LLM requests and responses.

    TODO(phase-2): Implement common policies (rate limit, cache, retry)
    TODO(phase-2): Add policy chaining
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the policy."""

    @abstractmethod
    async def apply(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Apply the policy to a function call.

        Args:
            func: The function to wrap.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the function call.
        """
        raise NotImplementedError("apply() not implemented in Phase 1")

    @abstractmethod
    async def on_request(self, request: Any) -> Any:
        """Hook called before sending a request.

        Args:
            request: The request object.

        Returns:
            The (possibly modified) request.
        """
        raise NotImplementedError("on_request() not implemented in Phase 1")

    @abstractmethod
    async def on_response(self, response: Any) -> Any:
        """Hook called after receiving a response.

        Args:
            response: The response object.

        Returns:
            The (possibly modified) response.
        """
        raise NotImplementedError("on_response() not implemented in Phase 1")
