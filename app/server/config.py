import logging
import os
from pathlib import Path
from typing import Union

import tomllib
from glowplug import MsSqlSettings
from pydantic_settings import BaseSettings

DbConfig = Union[MsSqlSettings]


class Config(BaseSettings):
    debug: bool = False
    db: DbConfig


def _load_config(path: str = os.getenv("CONFIG_PATH", "config.toml")) -> Config:
    """Load the configuration from a TOML file."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw_cfg = Path(path).read_text()
    cfg = tomllib.loads(raw_cfg)
    return Config.model_validate(cfg)


# The global app configuration
config = _load_config()

# Set up logging
logging.basicConfig(level=logging.DEBUG if config.debug else logging.INFO)
