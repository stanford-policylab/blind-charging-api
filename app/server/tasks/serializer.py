from kombu.utils.json import register_type as _register_json_type
from pydantic import BaseModel


def register_type(t: BaseModel):
    _register_json_type(t, t.__name__, t.model_dump, t.model_validate)
