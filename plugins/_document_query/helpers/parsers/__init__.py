"""Document parser registry."""
from .base import BaseParser
from .pdf import PdfParser
from .html import HtmlParser
from .text import TextParser
from .image import ImageParser
from .unstructured import UnstructuredParser

_PARSERS = [PdfParser(), HtmlParser(), TextParser(), ImageParser(), UnstructuredParser()]

def get_parser_for_mimetype(mimetype: str) -> BaseParser | None:
    for parser in _PARSERS:
        if parser.can_handle(mimetype):
            return parser
    return None

__all__ = ["BaseParser", "PdfParser", "HtmlParser", "TextParser", "ImageParser", "UnstructuredParser", "get_parser_for_mimetype"]
