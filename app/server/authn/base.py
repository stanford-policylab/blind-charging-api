from abc import ABC, abstractmethod

from fastapi import Request


class NotAuthenticated(Exception):
    """Raised when a request is not authenticated."""

    pass


class BaseAuthnDriver(ABC):
    @abstractmethod
    def validate_request(self, request: Request):
        """Validate an incoming request.

        Args:
            request (Request): The incoming request.

        Raises:
            NotAuthenticated: If the request is not authenticated
        """
        ...
