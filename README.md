# fetcharoo

[![Tests](https://github.com/MALathon/fetcharoo/actions/workflows/test.yml/badge.svg)](https://github.com/MALathon/fetcharoo/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for discovering, downloading, and tracking PDF documents from websites — with persistent state, change monitoring, and AI agent integration.

## What fetcharoo does

**Download PDFs** from websites with recursive crawling, filtering, merging, and concurrent downloads.

**Track documents over time** with a persistent SQLite catalog that remembers every PDF it has ever seen — content hashes, metadata, first/last seen dates.

**Detect changes** by diffing the current state of a site against the catalog. Know instantly what's new, changed, or removed.

**Integrate with AI agents** via an MCP server that exposes document discovery and tracking as tools for Claude and other AI systems.

## Features

### Core
- Download PDFs from webpages with recursive crawling (up to 5 levels)
- Merge PDFs into a single file or save separately
- Smart merge ordering (numeric, alphabetical, custom sort keys)
- Automatic URL deduplication across pages
- PDF filtering by filename pattern, URL pattern, and file size
- Dry-run mode to preview before downloading
- Progress bars with tqdm
- Configurable timeouts, rate limiting, and request delays

### Concurrent Downloads
- Parallel downloading with configurable thread pool
- Thread-safe rate limiting shared across workers
- 3-5x speedup on bulk downloads

### Persistent Document Catalog
- SQLite-backed tracking of every document across runs
- Content-hash-based change detection (SHA-256)
- Cross-URL deduplication (same PDF at different URLs)
- PDF metadata extraction (title, author, page count, creation date)
- Run history with diff summaries
- Export as JSON or CSV
- Search by URL or filename

### Watch Mode
- **One-shot diff** (`fetcharoo diff`) — cron-friendly, compare current state against catalog
- **Continuous watch** (`fetcharoo watch`) — poll at intervals, notify on changes
- Notifications: stdout, JSON, webhook (POST), shell command
- Git-like diff output: `+` new, `~` changed, `-` removed

### MCP Server
- Expose fetcharoo as an MCP server for AI agent integration
- Tools: `discover_pdfs`, `download_pdfs`, `catalog_query`, `catalog_diff`, `catalog_search`, `get_document_metadata`, `find_duplicate_documents`
- Stateful: AI agents get persistent memory of document history
- Optional dependency — install with `pip install fetcharoo[mcp]`

### Site Schemas
- Pre-built configurations for common document repositories
- Auto-detection: `--schema auto` matches URL to optimal settings
- Built-in schemas: arXiv, IETF RFCs, SEC EDGAR, W3C, Federal Register
- Each schema provides: URL patterns, filtering rules, rate limits, sort strategy

### Security
- Domain restriction for recursive crawling (SSRF protection)
- Path traversal protection on filenames
- Rate limiting between requests
- URL validation (http/https only)
- robots.txt compliance (optional)
- Custom User-Agent support

## Requirements

- Python 3.10 or higher
- Dependencies: `requests`, `pymupdf`, `beautifulsoup4`, `tqdm`

## Installation

```sh
pip install fetcharoo

# With MCP server support:
pip install fetcharoo[mcp]
```

### From source

```sh
git clone https://github.com/MALathon/fetcharoo.git
cd fetcharoo
poetry install
```

## Command-Line Interface

### Download PDFs

```sh
# Download PDFs from a webpage
fetcharoo https://example.com

# Recursive crawl + merge into one file
fetcharoo https://example.com -d 2 -m

# Parallel download with 10 workers
fetcharoo https://example.com --concurrent --max-workers 10

# Merge with numeric sorting and custom filename
fetcharoo https://example.com -m --sort-by numeric --output-name "textbook.pdf"

# Filter by filename pattern
fetcharoo https://example.com --include "report*.pdf" --exclude "*draft*"

# Dry run (list PDFs without downloading)
fetcharoo https://example.com --dry-run

# Use auto-detected site schema
fetcharoo https://arxiv.org/abs/2301.00001 --schema auto

# Track downloads in the persistent catalog
fetcharoo https://example.com --catalog
```

### Monitor for Changes

```sh
# One-shot diff: what's new since last check? (great for cron)
fetcharoo diff https://example.com

# Continuous watch: check every hour
fetcharoo watch https://example.com --interval 3600

# Watch with webhook notification
fetcharoo watch https://example.com --notify webhook --webhook https://hooks.example.com/notify

# Watch with shell command on change
fetcharoo watch https://example.com --notify command --on-command "echo 'New docs found!'"

# JSON output for piping
fetcharoo diff https://example.com --format json
```

### Manage the Catalog

```sh
# Show all tracked documents
fetcharoo catalog show

# Export as JSON or CSV
fetcharoo catalog export --format json
fetcharoo catalog export --format csv

# Search documents
fetcharoo catalog search "annual report"

# View run history
fetcharoo catalog runs

# Find duplicate documents (same content, different URLs)
fetcharoo catalog duplicates
```

### Site Schemas

```sh
# List available schemas
fetcharoo schemas list

# Check which schema matches a URL
fetcharoo schemas match https://arxiv.org/abs/2301.00001
```

### MCP Server

```sh
# Start the MCP server (for AI agent integration)
fetcharoo mcp serve
```

### All Download Options

| Option | Description |
|--------|-------------|
| `-o, --output DIR` | Output directory (default: output) |
| `-d, --depth N` | Recursion depth (default: 0) |
| `-m, --merge` | Merge all PDFs into a single file |
| `--output-name FILENAME` | Custom filename for merged PDF |
| `--sort-by STRATEGY` | Sort: `numeric`, `alpha`, `alpha_desc`, `none` |
| `--dry-run` | List PDFs without downloading |
| `--concurrent` | Download in parallel |
| `--max-workers N` | Max parallel threads (default: 5) |
| `--catalog` | Track in persistent catalog |
| `--catalog-db PATH` | Custom catalog database path |
| `--schema NAME` | Use site schema (`auto` for auto-detect) |
| `--delay SECONDS` | Delay between requests (default: 0.5) |
| `--timeout SECONDS` | Request timeout (default: 30) |
| `--user-agent STRING` | Custom User-Agent |
| `--respect-robots` | Respect robots.txt |
| `--progress` | Show progress bars |
| `-q, --quiet` | Less output (`-qq` for even quieter) |
| `-v, --verbose` | More output (`-vv` for debug) |
| `--include PATTERN` | Include filename pattern |
| `--exclude PATTERN` | Exclude filename pattern |
| `--min-size BYTES` | Minimum PDF size |
| `--max-size BYTES` | Maximum PDF size |

## Python API

### Quick Start

```python
from fetcharoo import download_pdfs_from_webpage

# Download PDFs — simple
download_pdfs_from_webpage('https://example.com', write_dir='output')

# Download with concurrent workers
download_pdfs_from_webpage(
    'https://example.com',
    recursion_depth=2,
    mode='merge',
    concurrent=True,
    max_workers=10,
    show_progress=True,
)
```

### Document Catalog

```python
from fetcharoo import DocumentCatalog

catalog = DocumentCatalog()  # defaults to ~/.fetcharoo/catalog.db

# Track a document
catalog.upsert_document(
    'https://example.com/report.pdf',
    content=pdf_bytes,
    source_page='https://example.com',
    filename='report.pdf',
)

# Search
results = catalog.search('annual report')

# Find duplicates (same content at different URLs)
dupes = catalog.find_duplicates()

# Diff against current state
diff = catalog.diff(['https://example.com/a.pdf', 'https://example.com/b.pdf'])
print(f"New: {len(diff.new)}, Removed: {len(diff.removed)}")

# Export
print(catalog.export_json())
print(catalog.export_csv())
```

### Watch Mode

```python
from fetcharoo import DocumentCatalog, DocumentWatcher

catalog = DocumentCatalog()
watcher = DocumentWatcher('https://example.com', catalog, recursion_depth=1)

# One-shot check
diff = watcher.check_once()
for doc in diff.new:
    print(f"New: {doc.url}")

# Or use the convenience function
from fetcharoo import diff_once
diff = diff_once('https://example.com', catalog)
```

### Site Schemas

```python
from fetcharoo import find_schema, list_schemas

# Auto-detect schema for a URL
schema = find_schema('https://arxiv.org/abs/2301.00001')
print(schema.name)           # 'arxiv'
print(schema.request_delay)  # 1.0 (arXiv rate-limits)

# List all available schemas
for s in list_schemas():
    print(f"{s.name}: {s.description}")
```

### Filtering

```python
from fetcharoo import download_pdfs_from_webpage, FilterConfig

filter_config = FilterConfig(
    filename_include=['report*.pdf', 'annual*.pdf'],
    filename_exclude=['*draft*', '*temp*'],
    url_include=['*/reports/*'],
    url_exclude=['*/archive/*'],
    min_size=10_000,      # 10KB minimum
    max_size=50_000_000,  # 50MB maximum
)

download_pdfs_from_webpage(
    'https://example.com',
    filter_config=filter_config,
)
```

### ProcessResult

```python
from fetcharoo import download_pdfs_from_webpage

result = download_pdfs_from_webpage('https://example.com')

print(result.success)          # bool
print(result.downloaded_count) # int
print(result.failed_count)     # int
print(result.filtered_count)   # int
print(result.files_created)    # List[str]
print(result.errors)           # List[str]

if result:  # truthy when successful
    print("Done!")
```

## MCP Server Configuration

Add fetcharoo to your Claude Code or MCP client configuration:

```json
{
  "mcpServers": {
    "fetcharoo": {
      "command": "fetcharoo",
      "args": ["mcp", "serve"]
    }
  }
}
```

Once connected, AI agents can use these tools:

| Tool | Description |
|------|-------------|
| `discover_pdfs` | Find all PDFs on a URL with filtering |
| `download_pdfs` | Download with full reliability (retry, rate limit, dedup) |
| `catalog_query` | Query persistent document memory |
| `catalog_diff` | What's changed since last check? |
| `catalog_search` | Search across all tracked documents |
| `get_document_metadata` | Detailed info about a tracked document |
| `find_duplicate_documents` | Same content at different URLs |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

Developed by Mark A. Lifson, Ph.D.
