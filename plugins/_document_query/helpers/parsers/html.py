"""HTML parser using Markdownify transformer."""

from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_core.documents import Document

from helpers import files
from .base import BaseParser


class HtmlParser(BaseParser):
    mimetypes = ["text/html"]

    def _parse_sync(self, document_uri: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            parts = AsyncHtmlLoader(web_path=document_uri).load()
        elif scheme == "file":
            content = files.read_file_bin(document_uri).decode("utf-8")
            parts = [Document(page_content=content, metadata={"source": document_uri})]
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")
        return "\n".join(e.page_content for e in MarkdownifyTransformer().transform_documents(parts))
