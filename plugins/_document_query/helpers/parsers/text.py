"""Plain text and config document parser."""

from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_core.documents import Document

from helpers import files
from .base import BaseParser


class TextParser(BaseParser):
    mimetypes = [
        "text/", "application/json", "application/yaml", "application/x-yaml",
        "application/xml", "application/toml", "application/x-toml",
        "application/javascript", "application/typescript",
        "application/x-sh", "application/x-shellscript",
    ]

    def _parse_sync(self, document_uri: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            elements = AsyncHtmlLoader(web_path=document_uri).load()
        elif scheme == "file":
            content = files.read_file_bin(document_uri).decode("utf-8")
            elements = [Document(page_content=content, metadata={"source": document_uri})]
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")
        return "\n".join(e.page_content for e in elements)
