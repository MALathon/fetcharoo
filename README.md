# fetcharoo

[![Tests](https://github.com/MALathon/fetcharoo/actions/workflows/test.yml/badge.svg)](https://github.com/MALathon/fetcharoo/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for downloading PDF files from webpages with support for recursive link following, PDF merging, and security hardening.

## Features

- Download PDF files from a specified webpage
- Recursive crawling with configurable depth (up to 5 levels)
- Merge downloaded PDFs into a single file or save separately
- **Security hardening**: Domain restriction, path traversal protection, rate limiting
- Configurable timeouts and request delays
- Simple, easy-to-use Python API

## Requirements

- Python 3.10 or higher
- Dependencies: `requests`, `pymupdf`, `beautifulsoup4`

## Installation

### Using pip

```sh
pip install fetcharoo
```

### Using Poetry

```sh
poetry add fetcharoo
```

### From source

```sh
git clone https://github.com/MALathon/fetcharoo.git
cd fetcharoo
poetry install
```

## Quick Start

```python
from fetcharoo import download_pdfs_from_webpage

# Download PDFs from a webpage and merge them into a single file
download_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=1,
    mode='merge',
    write_dir='output'
)
```

## Usage

### Basic Usage

```python
from fetcharoo import download_pdfs_from_webpage

# Download and save PDFs as separate files
download_pdfs_from_webpage(
    url='https://example.com/documents',
    recursion_depth=0,  # Only search the specified page
    mode='separate',
    write_dir='downloads'
)
```

### With Security Options

```python
from fetcharoo import download_pdfs_from_webpage

# Restrict crawling to specific domains
download_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=2,
    mode='merge',
    write_dir='output',
    allowed_domains={'example.com', 'docs.example.com'},
    request_delay=1.0,  # 1 second between requests
    timeout=60  # 60 second timeout
)
```

### Finding PDFs Without Downloading

```python
from fetcharoo import find_pdfs_from_webpage

# Just get the list of PDF URLs
pdf_urls = find_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=1
)

for url in pdf_urls:
    print(url)
```

### Processing PDFs Separately

```python
from fetcharoo import find_pdfs_from_webpage, process_pdfs

# Find PDFs first
pdf_urls = find_pdfs_from_webpage('https://example.com')

# Then process them
if pdf_urls:
    success = process_pdfs(
        pdf_links=pdf_urls,
        write_dir='output',
        mode='separate'
    )
```

## API Reference

### `download_pdfs_from_webpage()`

Main function to find and download PDFs from a webpage.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | The webpage URL to search |
| `recursion_depth` | int | 0 | How many levels of links to follow (max 5) |
| `mode` | str | 'separate' | 'merge' or 'separate' |
| `write_dir` | str | 'output' | Output directory for PDFs |
| `allowed_domains` | set | None | Restrict crawling to these domains |
| `request_delay` | float | 0.5 | Seconds between requests |
| `timeout` | int | 30 | Request timeout in seconds |

### `find_pdfs_from_webpage()`

Find PDF URLs without downloading.

### `process_pdfs()`

Download and save a list of PDF URLs.

### Utility Functions

- `merge_pdfs()` - Merge multiple PDF documents
- `is_valid_url()` - Validate URL format and scheme
- `is_safe_domain()` - Check if domain is allowed
- `sanitize_filename()` - Prevent path traversal attacks

## Security Features

fetcharoo includes several security measures:

- **Domain restriction**: Limit recursive crawling to specified domains (SSRF protection)
- **Path traversal protection**: Sanitizes filenames to prevent directory escape
- **Rate limiting**: Configurable delays between requests
- **Timeout handling**: Prevents hanging on slow servers
- **URL validation**: Only allows http/https schemes

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
