"""PDF parser with PyMuPDF primary and Tesseract OCR fallback."""

import os
import tempfile

from langchain_community.document_loaders.pdf import PyMuPDFLoader
from langchain_community.document_loaders.parsers.images import TesseractBlobParser
from langchain_core.documents import Document

from helpers import files
from helpers.print_style import PrintStyle

from .base import BaseParser


class PdfParser(BaseParser):
    mimetypes = ["application/pdf"]

    def _parse_sync(self, document_uri: str, scheme: str) -> str:
        temp_file_path = ""
        if scheme == "file":
            file_content_bytes = files.read_file_bin(document_uri)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                f.write(file_content_bytes)
                temp_file_path = f.name
        elif scheme in ["http", "https"]:
            import requests
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                resp = requests.get(document_uri, timeout=10.0)
                if resp.status_code != 200:
                    raise ValueError(f"Failed to download PDF: {resp.status_code}")
                f.write(resp.content)
                temp_file_path = f.name
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        if not os.path.exists(temp_file_path):
            raise ValueError(f"Temporary file not found: {temp_file_path}")
        try:
            contents = self._parse_with_pymupdf(temp_file_path)
            if not contents:
                contents = self._parse_with_ocr(temp_file_path)
            return contents
        finally:
            os.unlink(temp_file_path)

    def _parse_with_pymupdf(self, file_path: str) -> str:
        try:
            loader = PyMuPDFLoader(
                file_path, mode="single", extract_tables="markdown",
                extract_images=True, images_inner_format="text",
                images_parser=TesseractBlobParser(), pages_delimiter="\n",
            )
            return "\n".join(e.page_content for e in loader.load())
        except Exception as e:
            PrintStyle.error(f"PyMuPDF parsing failed: {e}")
            return ""

    def _parse_with_ocr(self, file_path: str) -> str:
        import pdf2image, pytesseract
        PrintStyle.debug(f"FALLBACK: OCR for {file_path}")
        pages = pdf2image.convert_from_path(file_path)
        return "\n\n".join(pytesseract.image_to_string(p) for p in pages)
