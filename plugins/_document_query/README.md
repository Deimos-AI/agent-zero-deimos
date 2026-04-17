# Document Query Plugin

Load, parse, index, and Q&A over local and remote documents with configurable
timeouts and thread-safe parsers.

## Features

- **Strategy-pattern parsers** - MIME-type routing to dedicated parser classes
- **Thread-safe execution** - all sync parsers offloaded to asyncio.to_thread
- **Configurable timeouts** - per-document and gather-level timeouts
- **Expanded format support** - PDF, HTML, text, YAML, XML, TOML, JS, TS, images, and catch-all Unstructured

## Configuration

See default_config.yaml for all options. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| fetch_timeout | 30 | HTTP fetch timeout (seconds) |
| per_document_timeout | 60 | Max time for a single document parse |
| gather_timeout | 120 | Max time for all documents combined |
| chunk_size | 1000 | Text splitter chunk size |
| chunk_overlap | 100 | Text splitter overlap |
| search_threshold | 0.5 | Similarity search threshold |
| thread_offload | true | Offload sync parsers to thread pool |

## Parsers

| Parser | MIME Types | Backend |
|--------|-----------|---------|
| PdfParser | application/pdf | PyMuPDF + Tesseract OCR fallback |
| HtmlParser | text/html | Markdownify transformer |
| TextParser | text/*, application/json, YAML, XML, TOML, JS, TS, shell | Direct read |
| ImageParser | image/* | UnstructuredLoader |
| UnstructuredParser | * (catch-all) | UnstructuredLoader hi-res |

## Adding a new parser

1. Create helpers/parsers/<format>.py extending BaseParser
2. Set mimetypes class attribute
3. Implement _parse_sync(document_uri, scheme)
4. Register in helpers/parsers/__init__.py
