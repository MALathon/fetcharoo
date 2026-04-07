"""
Persistent document catalog for fetcharoo.

Tracks every PDF fetcharoo has ever seen across runs using SQLite.
Provides content-hash-based change detection, cross-URL deduplication,
run history, and metadata extraction.
"""

import csv
import hashlib
import io
import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pymupdf

logger = logging.getLogger('fetcharoo')

# Current schema version for migrations
CATALOG_SCHEMA_VERSION = 1


@dataclass
class DocumentRecord:
    """A single document tracked in the catalog."""
    id: str
    url: str
    filename: Optional[str] = None
    content_hash: Optional[str] = None
    size_bytes: Optional[int] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    last_changed: Optional[str] = None
    status: str = 'active'
    source_page: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class RunRecord:
    """Summary of a single catalog run."""
    id: Optional[int] = None
    url: str = ''
    timestamp: Optional[str] = None
    documents_found: int = 0
    documents_new: int = 0
    documents_changed: int = 0
    documents_removed: int = 0


@dataclass
class DiffResult:
    """Result of comparing current state against catalog."""
    new: List[DocumentRecord] = field(default_factory=list)
    changed: List[DocumentRecord] = field(default_factory=list)
    removed: List[DocumentRecord] = field(default_factory=list)
    unchanged: List[DocumentRecord] = field(default_factory=list)


def _url_id(url: str) -> str:
    """Generate a deterministic ID for a URL."""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]


def _content_hash(content: bytes) -> str:
    """Generate a SHA-256 hash of PDF content."""
    return hashlib.sha256(content).hexdigest()


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def extract_pdf_metadata(content: bytes) -> Dict[str, Any]:
    """
    Extract metadata from PDF content using PyMuPDF.

    Args:
        content: Raw PDF bytes.

    Returns:
        Dict with keys like title, author, page_count, creation_date.
    """
    metadata: Dict[str, Any] = {}
    try:
        doc = pymupdf.Document(stream=content, filetype="pdf")
        meta = doc.metadata or {}
        metadata['title'] = meta.get('title', '') or ''
        metadata['author'] = meta.get('author', '') or ''
        metadata['subject'] = meta.get('subject', '') or ''
        metadata['creator'] = meta.get('creator', '') or ''
        metadata['producer'] = meta.get('producer', '') or ''
        metadata['creation_date'] = meta.get('creationDate', '') or ''
        metadata['page_count'] = doc.page_count
        doc.close()
    except Exception as e:
        logger.debug(f"Could not extract PDF metadata: {e}")
    return metadata


class DocumentCatalog:
    """
    SQLite-backed persistent document catalog.

    Tracks documents across runs with content-hash-based change detection.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: Path to SQLite database file. Defaults to ~/.fetcharoo/catalog.db
        """
        if db_path is None:
            catalog_dir = os.path.join(os.path.expanduser('~'), '.fetcharoo')
            os.makedirs(catalog_dir, exist_ok=True)
            db_path = os.path.join(catalog_dir, 'catalog.db')

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    filename TEXT,
                    content_hash TEXT,
                    size_bytes INTEGER,
                    first_seen TEXT,
                    last_seen TEXT,
                    last_changed TEXT,
                    status TEXT DEFAULT 'active',
                    source_page TEXT,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    timestamp TEXT,
                    documents_found INTEGER DEFAULT 0,
                    documents_new INTEGER DEFAULT 0,
                    documents_changed INTEGER DEFAULT 0,
                    documents_removed INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
                CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
                CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
                CREATE INDEX IF NOT EXISTS idx_runs_url ON runs(url);
            """)

    def upsert_document(
        self,
        url: str,
        content: Optional[bytes] = None,
        source_page: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> DocumentRecord:
        """
        Insert or update a document in the catalog.

        Args:
            url: The document URL.
            content: Raw PDF bytes (for hashing and metadata extraction).
            source_page: The page where this PDF was discovered.
            filename: The PDF filename.

        Returns:
            The upserted DocumentRecord.
        """
        doc_id = _url_id(url)
        now = _now_iso()
        c_hash = _content_hash(content) if content else None
        size = len(content) if content else None
        metadata = extract_pdf_metadata(content) if content else {}

        existing = self._get_raw(doc_id)
        if existing is None:
            # New document
            record = DocumentRecord(
                id=doc_id,
                url=url,
                filename=filename,
                content_hash=c_hash,
                size_bytes=size,
                first_seen=now,
                last_seen=now,
                last_changed=now,
                status='active',
                source_page=source_page,
                metadata=metadata,
            )
            self._insert(record)
        else:
            # Existing document — check for changes
            old_hash = existing['content_hash']
            changed = c_hash is not None and old_hash != c_hash
            record = DocumentRecord(
                id=doc_id,
                url=url,
                filename=filename or existing['filename'],
                content_hash=c_hash or existing['content_hash'],
                size_bytes=size if size is not None else existing['size_bytes'],
                first_seen=existing['first_seen'],
                last_seen=now,
                last_changed=now if changed else existing['last_changed'],
                status='active',
                source_page=source_page or existing['source_page'],
                metadata=metadata or json.loads(existing['metadata'] or '{}'),
            )
            self._update(record)

        return record

    def record_discovery(
        self,
        url: str,
        source_page: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> DocumentRecord:
        """
        Record that a PDF URL was discovered (without downloading content).

        Args:
            url: The document URL.
            source_page: The page where this PDF was discovered.
            filename: The PDF filename.

        Returns:
            The DocumentRecord.
        """
        return self.upsert_document(url, content=None, source_page=source_page, filename=filename)

    def mark_removed(self, url: str) -> None:
        """Mark a document as removed (no longer found at its URL)."""
        doc_id = _url_id(url)
        with self._conn:
            self._conn.execute(
                "UPDATE documents SET status = 'removed', last_seen = ? WHERE id = ?",
                (_now_iso(), doc_id)
            )

    def get_document(self, url: str) -> Optional[DocumentRecord]:
        """Get a document record by URL."""
        doc_id = _url_id(url)
        row = self._get_raw(doc_id)
        if row is None:
            return None
        return self._row_to_record(row)

    def get_active_documents(self, source_page: Optional[str] = None) -> List[DocumentRecord]:
        """
        Get all active documents, optionally filtered by source page.

        Args:
            source_page: If provided, only return documents from this source page.
        """
        if source_page:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE status = 'active' AND source_page = ? ORDER BY url",
                (source_page,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE status = 'active' ORDER BY url"
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_all_documents(self) -> List[DocumentRecord]:
        """Get all documents regardless of status."""
        rows = self._conn.execute(
            "SELECT * FROM documents ORDER BY url"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def find_duplicates(self) -> Dict[str, List[DocumentRecord]]:
        """
        Find documents with the same content hash but different URLs.

        Returns:
            Dict mapping content_hash to list of DocumentRecords sharing that hash.
        """
        rows = self._conn.execute("""
            SELECT content_hash, COUNT(*) as cnt FROM documents
            WHERE content_hash IS NOT NULL AND status = 'active'
            GROUP BY content_hash HAVING cnt > 1
        """).fetchall()

        duplicates: Dict[str, List[DocumentRecord]] = {}
        for row in rows:
            hash_val = row['content_hash']
            doc_rows = self._conn.execute(
                "SELECT * FROM documents WHERE content_hash = ? AND status = 'active'",
                (hash_val,)
            ).fetchall()
            duplicates[hash_val] = [self._row_to_record(r) for r in doc_rows]
        return duplicates

    def search(self, query: str) -> List[DocumentRecord]:
        """
        Search documents by URL or filename substring.

        Args:
            query: Search string (matched against URL and filename).
        """
        pattern = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE (url LIKE ? OR filename LIKE ?) ORDER BY url",
            (pattern, pattern)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def diff(self, current_urls: List[str]) -> DiffResult:
        """
        Compare a list of currently discovered URLs against the catalog.

        Args:
            current_urls: URLs found in the current crawl.

        Returns:
            DiffResult with new, changed, removed, and unchanged documents.
        """
        result = DiffResult()
        current_set = set(current_urls)
        known_docs = {doc.url: doc for doc in self.get_active_documents()}

        for url in current_urls:
            if url in known_docs:
                result.unchanged.append(known_docs[url])
            else:
                result.new.append(DocumentRecord(
                    id=_url_id(url),
                    url=url,
                    status='new',
                ))

        for url, doc in known_docs.items():
            if url not in current_set:
                result.removed.append(doc)

        return result

    def record_run(self, url: str, diff: DiffResult) -> RunRecord:
        """
        Record a run in the catalog.

        Args:
            url: The source URL that was crawled.
            diff: The DiffResult from this run.

        Returns:
            The RunRecord.
        """
        run = RunRecord(
            url=url,
            timestamp=_now_iso(),
            documents_found=len(diff.new) + len(diff.unchanged) + len(diff.changed),
            documents_new=len(diff.new),
            documents_changed=len(diff.changed),
            documents_removed=len(diff.removed),
        )
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO runs (url, timestamp, documents_found, documents_new, documents_changed, documents_removed) VALUES (?, ?, ?, ?, ?, ?)",
                (run.url, run.timestamp, run.documents_found, run.documents_new, run.documents_changed, run.documents_removed)
            )
            run.id = cursor.lastrowid
        return run

    def get_runs(self, url: Optional[str] = None, limit: int = 20) -> List[RunRecord]:
        """Get recent runs, optionally filtered by URL."""
        if url:
            rows = self._conn.execute(
                "SELECT * FROM runs WHERE url = ? ORDER BY timestamp DESC LIMIT ?",
                (url, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [
            RunRecord(
                id=r['id'], url=r['url'], timestamp=r['timestamp'],
                documents_found=r['documents_found'], documents_new=r['documents_new'],
                documents_changed=r['documents_changed'], documents_removed=r['documents_removed']
            )
            for r in rows
        ]

    def export_json(self) -> str:
        """Export the entire catalog as a JSON string."""
        docs = self.get_all_documents()
        data = []
        for doc in docs:
            d = {
                'id': doc.id,
                'url': doc.url,
                'filename': doc.filename,
                'content_hash': doc.content_hash,
                'size_bytes': doc.size_bytes,
                'first_seen': doc.first_seen,
                'last_seen': doc.last_seen,
                'last_changed': doc.last_changed,
                'status': doc.status,
                'source_page': doc.source_page,
                'metadata': doc.metadata,
            }
            data.append(d)
        return json.dumps(data, indent=2)

    def export_csv(self) -> str:
        """Export the entire catalog as a CSV string."""
        docs = self.get_all_documents()
        output = io.StringIO()
        fieldnames = [
            'id', 'url', 'filename', 'content_hash', 'size_bytes',
            'first_seen', 'last_seen', 'last_changed', 'status',
            'source_page', 'page_count', 'title', 'author'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for doc in docs:
            meta = doc.metadata or {}
            writer.writerow({
                'id': doc.id,
                'url': doc.url,
                'filename': doc.filename,
                'content_hash': doc.content_hash,
                'size_bytes': doc.size_bytes,
                'first_seen': doc.first_seen,
                'last_seen': doc.last_seen,
                'last_changed': doc.last_changed,
                'status': doc.status,
                'source_page': doc.source_page,
                'page_count': meta.get('page_count', ''),
                'title': meta.get('title', ''),
                'author': meta.get('author', ''),
            })
        return output.getvalue()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    @property
    def document_count(self) -> int:
        """Total number of documents in the catalog."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row['cnt']

    @property
    def active_count(self) -> int:
        """Number of active documents in the catalog."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE status = 'active'"
        ).fetchone()
        return row['cnt']

    # --- Internal helpers ---

    def _get_raw(self, doc_id: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

    def _insert(self, record: DocumentRecord) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT INTO documents
                   (id, url, filename, content_hash, size_bytes, first_seen,
                    last_seen, last_changed, status, source_page, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (record.id, record.url, record.filename, record.content_hash,
                 record.size_bytes, record.first_seen, record.last_seen,
                 record.last_changed, record.status, record.source_page,
                 json.dumps(record.metadata or {}))
            )

    def _update(self, record: DocumentRecord) -> None:
        with self._conn:
            self._conn.execute(
                """UPDATE documents SET
                   url=?, filename=?, content_hash=?, size_bytes=?,
                   last_seen=?, last_changed=?, status=?, source_page=?, metadata=?
                   WHERE id=?""",
                (record.url, record.filename, record.content_hash,
                 record.size_bytes, record.last_seen, record.last_changed,
                 record.status, record.source_page,
                 json.dumps(record.metadata or {}), record.id)
            )

    def _row_to_record(self, row: sqlite3.Row) -> DocumentRecord:
        meta = json.loads(row['metadata'] or '{}')
        return DocumentRecord(
            id=row['id'],
            url=row['url'],
            filename=row['filename'],
            content_hash=row['content_hash'],
            size_bytes=row['size_bytes'],
            first_seen=row['first_seen'],
            last_seen=row['last_seen'],
            last_changed=row['last_changed'],
            status=row['status'],
            source_page=row['source_page'],
            metadata=meta,
        )
