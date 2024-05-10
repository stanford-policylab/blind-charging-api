import asyncio
import logging

import typer

from .config import config
from .db import Base

logger = logging.getLogger(__name__)

cli = typer.Typer()


@cli.command()
def create_db(wipe: bool = False) -> None:
    """Ensure the database exists.

    If `wipe` is True, drop the database first.

    Args:
        wipe (bool): Whether to drop the database first.
    """

    async def init_db():
        if not await config.db.driver.exists():
            logger.info("No database exists, creating a new one")
            await config.db.driver.create()
        else:
            logger.info("Database already exists")

        # Create the database
        if wipe:
            logger.info("Re-creating database tables")
        else:
            logger.info("Creating database tables")
        await config.db.driver.init(Base, drop_first=wipe)

    asyncio.run(init_db())

    # Stamp the revision as current so that future migrations will work.
    config.db.driver.alembic.stamp("head")
    logger.info("Database created successfully")


if __name__ == "__main__":
    cli()
