# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-10-04T19:25:33+00:00

# mypy: disable-error-code="name-defined"

import importlib
import logging
from typing import Any, Callable

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def _get_default_handler(slug: str) -> Callable:
    """Return a default handler that raises a 501 Not Implemented error.

    The error detail will include the slug of the handler that was not found.

    Args:
        slug (str): The slug of the handler that was not found.

    Returns:
        Callable: A handler that raises a 501 Not Implemented error.
    """

    def _handler(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f'Handler {slug} not implemented',
        )

    return _handler


class _EmptyModule:
    """An empty namespace for modules that don't exist."""

    pass


class _VHandler:
    """A dynamic handler for loading handlers for different tags.

    The virtual handler class will load a module with then name `tag`
    located in the `app.server.handlers` package. If the module is not found,
    a default handler is returned that raises a 501 Not Implemented error.

    For example, assuming the module `app.server.handlers.redact` exists with
    a function `get_redacted_text`, the following code will load and call
    the handler:

        redact_handler = _VHandler('redact')
        redact_handler.get_redacted_text('Hello, World!')
    """

    def __init__(self, tag: str):
        """Initialize the handler for the given tag.

        Args:
            tag (str): The name of the module to load.
        """
        self._tag = tag
        self._module = self._load_module(tag)

    def __getattr__(self, item: str) -> Callable:
        """Dynamically load the handler for the given item.

        Args:
            item (str): The name of the handler to get.

        Returns:
            Callable: The handler for the given item.
        """
        return self._get_handler(item)

    def _get_handler(self, name: str) -> Callable:
        """Get the handler by `name` from the loaded module.

        If the handler is not found, a default handler is returned that returns
        a 501 Not Implemented error.

        Args:
            name (str): The name of the handler to get.

        Returns:
            Callable: The handler for the given name.
        """
        handler = getattr(self._module, name, None)
        if handler:
            return handler

        slug = f"{self._tag}.{name}"
        logger.warning(f'No handler found for {slug}')
        return _get_default_handler(slug)

    def _load_module(self, name: str, pkg: str = 'app.server') -> Any:
        """Load the module specified by the given `name`.

        Modules should be located in the `.handlers` package, a child
        of the package defined by `pkg`.

        If the module doesn't exist, an empty placeholder is returned.

        Args:
            name (str): The module name.
            pkg (str): The package to load the module from.

        Returns:
            The module loaded by the given name.
        """
        subpkg = f'.handlers.{name}'
        try:
            logger.debug(f'Importing module for tag {name}')
            return importlib.import_module(subpkg, package=pkg)
        except ModuleNotFoundError:
            logger.warning(f'No module found for tag {name}!')
            return _EmptyModule()


# Define the virtual handlers for each router.
# Doesn't matter if the module doesn't exist; the default handler will return a 501 error.
experiments_handler = _VHandler('experiments')
operations_handler = _VHandler('operations')
redaction_handler = _VHandler('redaction')
review_handler = _VHandler('review')
