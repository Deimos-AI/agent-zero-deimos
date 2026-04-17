"""Document query helper with thread-safe parsers and configurable timeouts.

Extracted from the monolithic helpers/document_query.py into a plugin
with parser strategy pattern where every document parser is offloaded to
a thread pool and bounded by configurable timeouts.
"""

import asyncio
import json
import mimetypes
import os
from datetime import datetime
from typing import Callable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import aiohttp
from langchain.schema import SystemMessage, HumanMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from helpers import files, errors
from helpers.print_style import PrintStyle
from helpers.vector_db import VectorDB
from agent import Agent

from plugins._document_query.helpers.parsers import get_parser_for_mimetype


DEFAULT_SEARCH_THRESHOLD = 0.5


def _load_config(agent: Agent) -> dict:
    """Load plugin config with fallback to defaults."""
    from helpers.plugins import get_plugin_config
    return get_plugin_config("_document_query", agent=agent) or {}


class DocumentQueryStore:
    """FAISS Store for document query results."""

    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP = 100

    @staticmethod
    def get(agent: Agent):
        if not agent or not agent.config:
            raise ValueError("Agent and agent config must be provided")
        return DocumentQueryStore(agent)

    def __init__(self, agent: Agent):
        self.agent = agent
        self.vector_db: VectorDB | None = None
        self.config = _load_config(agent)

    @staticmethod
    def normalize_uri(uri: str) -> str:
        normalized = uri.strip()
        parsed = urlparse(normalized)
        scheme = parsed.scheme or "file"
        if scheme == "file":
            path = files.fix_dev_path(
                normalized.removeprefix("file://").removeprefix("file:")
            )
            normalized = f"file://{path}"
        elif scheme in ["http", "https"]:
            normalized = normalized.replace("http://", "https://")
        return normalized

    def init_vector_db(self):
        return VectorDB(self.agent, cache=True)

    async def add_document(
        self, text: str, document_uri: str, metadata: dict | None = None
    ) -> tuple[bool, list[str]]:
        document_uri = self.normalize_uri(document_uri)
        await self.delete_document(document_uri)
        doc_metadata = metadata or {}
        doc_metadata["document_uri"] = document_uri
        doc_metadata["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chunk_size = self.config.get("chunk_size", self.DEFAULT_CHUNK_SIZE)
        chunk_overlap = self.config.get("chunk_overlap", self.DEFAULT_CHUNK_OVERLAP)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(text)
        docs = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = doc_metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)
            docs.append(Document(page_content=chunk, metadata=chunk_metadata))
        if not docs:
            PrintStyle.error(f"No chunks created for document: {document_uri}")
            return False, []
        try:
            if not self.vector_db:
                self.vector_db = self.init_vector_db()
            ids = await self.vector_db.insert_documents(docs)
            PrintStyle.standard(f"Added document '{document_uri}' with {len(docs)} chunks")
            return True, ids
        except Exception as e:
            err_text = errors.format_error(e)
            PrintStyle.error(f"Error adding document '{document_uri}': {err_text}")
            return False, []

    async def get_document(self, document_uri: str) -> Optional[Document]:
        if not self.vector_db:
            return None
        document_uri = self.normalize_uri(document_uri)
        docs = await self._get_document_chunks(document_uri)
        if not docs:
            return None
        chunks = sorted(docs, key=lambda x: x.metadata.get("chunk_index", 0))
        full_content = "\n".join(chunk.page_content for chunk in chunks)
        metadata = chunks[0].metadata.copy()
        metadata.pop("chunk_index", None)
        metadata.pop("total_chunks", None)
        return Document(page_content=full_content, metadata=metadata)

    async def _get_document_chunks(self, document_uri: str) -> List[Document]:
        if not self.vector_db:
            return []
        document_uri = self.normalize_uri(document_uri)
        chunks = await self.vector_db.search_by_metadata(
            filter=f"document_uri == '{document_uri}'",
        )
        PrintStyle.standard(f"Found {len(chunks)} chunks for document: {document_uri}")
        return chunks

    async def document_exists(self, document_uri: str) -> bool:
        if not self.vector_db:
            return False
        document_uri = self.normalize_uri(document_uri)
        chunks = await self._get_document_chunks(document_uri)
        return len(chunks) > 0

    async def delete_document(self, document_uri: str) -> bool:
        if not self.vector_db:
            return False
        document_uri = self.normalize_uri(document_uri)
        chunks = await self.vector_db.search_by_metadata(
            filter=f"document_uri == '{document_uri}'",
        )
        if not chunks:
            return False
        ids_to_delete = [chunk.metadata["id"] for chunk in chunks]
        if ids_to_delete:
            dels = await self.vector_db.delete_documents_by_ids(ids_to_delete)
            PrintStyle.standard(f"Deleted document '{document_uri}' with {len(dels)} chunks")
            return True
        return False

    async def search_documents(
        self, query: str, limit: int = 10, threshold: float = 0.5, filter: str = ""
    ) -> List[Document]:
        if not self.vector_db:
            return []
        if not query:
            return []
        try:
            results = await self.vector_db.search_by_similarity_threshold(
                query=query, limit=limit, threshold=threshold, filter=filter
            )
            PrintStyle.standard(f"Search '{query}' returned {len(results)} results")
            return results
        except Exception as e:
            PrintStyle.error(f"Error searching documents: {str(e)}")
            return []

    async def search_document(
        self, document_uri: str, query: str, limit: int = 10, threshold: float = 0.5
    ) -> List[Document]:
        return await self.search_documents(
            query, limit, threshold, f"document_uri == '{document_uri}'"
        )

    async def list_documents(self) -> List[str]:
        if not self.vector_db:
            return []
        uris = set()
        for doc in self.vector_db.db.get_all_docs().values():
            if isinstance(doc.metadata, dict):
                uri = doc.metadata.get("document_uri")
                if uri:
                    uris.add(uri)
        return sorted(list(uris))


class DocumentQueryHelper:

    def __init__(
        self, agent: Agent, progress_callback: Callable[[str], None] | None = None
    ):
        self.agent = agent
        self.store = DocumentQueryStore.get(agent)
        self.progress_callback = progress_callback or (lambda x: None)
        self.store_lock = asyncio.Lock()
        self.config = _load_config(agent)

    async def document_qa(
        self, document_uris: List[str], questions: Sequence[str]
    ) -> Tuple[bool, str]:
        self.progress_callback(f"Starting Q&A process for {len(document_uris)} documents")
        await self.agent.handle_intervention()

        gather_timeout = self.config.get("gather_timeout", 120)
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *[self.document_get_content(uri, True) for uri in document_uris]
                ),
                timeout=gather_timeout,
            )
        except asyncio.TimeoutError:
            raise ValueError(f"Document indexing timed out after {gather_timeout}s")

        await self.agent.handle_intervention()
        search_threshold = self.config.get("search_threshold", DEFAULT_SEARCH_THRESHOLD)
        search_limit = self.config.get("search_limit", 100)
        selected_chunks = {}

        for question in questions:
            self.progress_callback(f"Optimizing query: {question}")
            await self.agent.handle_intervention()
            system_content = self.agent.parse_prompt("fw.document_query.optmimize_query.md")
            optimized_query = (
                await self.agent.call_utility_model(
                    system=system_content, message=f'Search Query: "{question}"',
                )
            ).strip()

            await self.agent.handle_intervention()
            self.progress_callback(f"Searching documents with query: {optimized_query}")
            normalized_uris = [self.store.normalize_uri(uri) for uri in document_uris]
            doc_filter = " or ".join(
                [f"document_uri == '{uri}'" for uri in normalized_uris]
            )
            chunks = await self.store.search_documents(
                query=optimized_query, limit=search_limit,
                threshold=search_threshold, filter=doc_filter,
            )
            self.progress_callback(f"Found {len(chunks)} chunks")
            for chunk in chunks:
                selected_chunks[chunk.metadata["id"]] = chunk

        if not selected_chunks:
            self.progress_callback("No relevant content found in the documents")
            content = f"!!! No content found for documents: {json.dumps(document_uris)} matching queries: {json.dumps(questions)}"
            return False, content

        self.progress_callback(
            f"Processing {len(questions)} questions in context of {len(selected_chunks)} chunks"
        )
        await self.agent.handle_intervention()
        questions_str = "\n".join([f" *  {question}" for question in questions])
        content = "\n\n----\n\n".join(
            [chunk.page_content for chunk in selected_chunks.values()]
        )
        qa_system_message = self.agent.parse_prompt("fw.document_query.system_prompt.md")
        qa_user_message = f"# Document:\n{content}\n\n# Queries:\n{questions_str}"
        ai_response, _reasoning = await self.agent.call_chat_model(
            messages=[
                SystemMessage(content=qa_system_message),
                HumanMessage(content=qa_user_message),
            ],
            explicit_caching=False,
        )
        self.progress_callback(f"Q&A process completed")
        return True, str(ai_response)

    async def document_get_content(
        self, document_uri: str, add_to_db: bool = False
    ) -> str:
        self.progress_callback(f"Fetching document content")
        await self.agent.handle_intervention()
        url = urlparse(document_uri)
        scheme = url.scheme or "file"
        mimetype, encoding = mimetypes.guess_type(document_uri)
        mimetype = mimetype or "application/octet-stream"

        if mimetype == "application/octet-stream":
            if url.scheme in ["http", "https"]:
                response = None
                retries = 0
                last_error = ""
                while not response and retries < 3:
                    try:
                        async with aiohttp.ClientSession() as session:
                            response = await session.head(
                                document_uri,
                                timeout=aiohttp.ClientTimeout(total=2.0),
                                allow_redirects=True,
                            )
                            if response.status > 399:
                                raise Exception(response.status)
                            break
                    except Exception as e:
                        await asyncio.sleep(1)
                        last_error = str(e)
                    retries += 1
                    await self.agent.handle_intervention()
                if not response:
                    raise ValueError(f"Document fetch error: {document_uri} ({last_error})")
                mimetype = response.headers["content-type"]
                if "content-length" in response.headers:
                    content_length = float(response.headers["content-length"]) / 1024 / 1024
                    if content_length > 50.0:
                        raise ValueError(f"Document exceeds max 50MB: {content_length} MB ({document_uri})")
                if mimetype and "; charset=" in mimetype:
                    mimetype = mimetype.split("; charset=")[0]

        if scheme == "file":
            try:
                document_uri = files.fix_dev_path(url.path)
            except Exception as e:
                raise ValueError(f"Invalid document path '{url.path}'") from e

        if encoding:
            raise ValueError(f"Compressed documents are unsupported '{encoding}' ({document_uri})")
        if mimetype == "application/octet-stream":
            raise ValueError(f"Unsupported document mimetype '{mimetype}' ({document_uri})")

        document_uri_norm = self.store.normalize_uri(document_uri)
        await self.agent.handle_intervention()
        exists = await self.store.document_exists(document_uri_norm)
        document_content = ""

        if not exists:
            await self.agent.handle_intervention()
            parser = get_parser_for_mimetype(mimetype)
            if parser is None:
                raise ValueError(f"No parser found for mimetype '{mimetype}' ({document_uri})")
            per_doc_timeout = self.config.get("per_document_timeout", 60)
            thread_offload = self.config.get("thread_offload", True)
            document_content = await parser.parse(
                document_uri=document_uri, scheme=scheme,
                timeout=per_doc_timeout, thread_offload=thread_offload,
            )
            if add_to_db:
                self.progress_callback(f"Indexing document")
                await self.agent.handle_intervention()
                async with self.store_lock:
                    success, ids = await self.store.add_document(document_content, document_uri_norm)
                if not success:
                    self.progress_callback(f"Failed to index document")
                    raise ValueError(f"Failed to index document: {document_uri_norm}")
                self.progress_callback(f"Indexed {len(ids)} chunks")
        else:
            await self.agent.handle_intervention()
            doc = await self.store.get_document(document_uri_norm)
            if doc:
                document_content = doc.page_content
            else:
                raise ValueError(f"Document not found: {document_uri_norm}")
        return document_content
