from functools import cached_property
from typing import Literal

from pydantic import BaseModel

from .base import BaseAuthnDriver


class NoAuthnConfig(BaseModel):
    method: Literal["none"] = "none"

    @cached_property
    def driver(self):
        return NoAuthnDriver()


class NoAuthnDriver(BaseAuthnDriver):
    def validate_request(self, request):
        pass
