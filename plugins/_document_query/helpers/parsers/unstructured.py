"""Catch-all parser using UnstructuredLoader."""

import os
import tempfile

from helpers import files
from .base import BaseParser

os.environ.setdefault("USER_AGENT", "@mixedbread-ai/unstructured")
from langchain_unstructured import UnstructuredLoader


class UnstructuredParser(BaseParser):
    mimetypes = ["*"]

    def _parse_sync(self, document_uri: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            loader = UnstructuredLoader(web_url=document_uri, mode="single", partition_via_api=False, strategy="hi_res")
            elements = loader.load()
        elif scheme == "file":
            content = files.read_file_bin(document_uri)
            _, ext = os.path.splitext(document_uri)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
                f.write(content)
                tmp = f.name
            try:
                loader = UnstructuredLoader(file_path=tmp, mode="single", partition_via_api=False, strategy="hi_res")
                elements = loader.load()
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")
        return "\n".join(e.page_content for e in elements)
