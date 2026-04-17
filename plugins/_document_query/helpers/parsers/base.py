"""Base parser with built-in thread offload and timeout."""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from helpers.print_style import PrintStyle


class BaseParser(ABC):
    """Abstract base for document parsers.

    Every parser runs synchronously but is automatically offloaded to a
    thread pool and bounded by a configurable timeout when called through
    parse(). This prevents any single parser from blocking the asyncio
    event loop.
    """

    mimetypes: list[str] = []

    def can_handle(self, mimetype: str) -> bool:
        """Return True if this parser supports *mimetype*."""
        for pattern in self.mimetypes:
            if pattern == "*":
                return True
            if pattern.endswith("/"):
                if mimetype.startswith(pattern):
                    return True
            elif mimetype == pattern:
                return True
        return False

    async def parse(
        self,
        document_uri: str,
        scheme: str,
        timeout: float = 60.0,
        thread_offload: bool = True,
    ) -> str:
        try:
            if thread_offload:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._parse_sync, document_uri, scheme),
                    timeout=timeout,
                )
            else:
                return await asyncio.wait_for(
                    self._parse_async(document_uri, scheme),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            PrintStyle.error(
                f"Parser {self.__class__.__name__} timed out after {timeout}s on {document_uri}"
            )
            raise ValueError(f"Document parsing timed out after {timeout}s: {document_uri}")

    async def _parse_async(self, document_uri: str, scheme: str) -> str:
        return self._parse_sync(document_uri, scheme)

    @abstractmethod
    def _parse_sync(self, document_uri: str, scheme: str) -> str:
        ...
