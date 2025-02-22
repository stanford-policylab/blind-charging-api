from abc import ABC, abstractmethod

from fastapi import Request

from ..time import NowFn, utcnow


class NotAuthenticated(Exception):
    """Raised when a request is not authenticated."""

    pass


class BaseAuthnDriver(ABC):
    @abstractmethod
    async def validate_request(
        self, request: Request, scopes: list[str], now: NowFn = utcnow
    ):
        """Validate an incoming request.

        Args:
            request (Request): The incoming request.
            scopes (list[str]): The required scopes.

        Raises:
            NotAuthenticated: If the request is not authenticated
        """
        ...
