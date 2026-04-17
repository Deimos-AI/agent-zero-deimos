"""Image parser — delegates to UnstructuredLoader."""
from .base import BaseParser
from .unstructured import UnstructuredParser


class ImageParser(BaseParser):
    mimetypes = ["image/"]
    def _parse_sync(self, document_uri: str, scheme: str) -> str:
        return UnstructuredParser()._parse_sync(document_uri, scheme)
