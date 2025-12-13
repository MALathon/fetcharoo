# fetcharoo

[![Tests](https://github.com/MALathon/fetcharoo/actions/workflows/test.yml/badge.svg)](https://github.com/MALathon/fetcharoo/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for downloading PDF files from webpages with support for recursive link following, PDF merging, and security hardening.

## Features

- Download PDF files from a specified webpage
- Recursive crawling with configurable depth (up to 5 levels)
- Merge downloaded PDFs into a single file or save separately
- **Command-line interface** for quick downloads
- **robots.txt compliance** for ethical web crawling
- **Custom User-Agent** support
- **Dry-run mode** to preview downloads
- **Progress bars** with tqdm integration
- **PDF filtering** by filename, URL patterns, and size
- **Security hardening**: Domain restriction, path traversal protection, rate limiting
- Configurable timeouts and request delays

## Requirements

- Python 3.10 or higher
- Dependencies: `requests`, `pymupdf`, `beautifulsoup4`, `tqdm`

## Installation

### Using pip

```sh
pip install fetcharoo
```

### From GitHub (latest)

```sh
pip install git+https://github.com/MALathon/fetcharoo.git
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

## Command-Line Interface

fetcharoo includes a CLI for quick PDF downloads:

```sh
# Download PDFs from a webpage
fetcharoo https://example.com

# Download with recursion and merge into one file
fetcharoo https://example.com -d 2 -m

# List PDFs without downloading (dry run)
fetcharoo https://example.com --dry-run

# Download with custom options
fetcharoo https://example.com -o my_pdfs --delay 1.0 --progress

# Filter PDFs by pattern
fetcharoo https://example.com --include "report*.pdf" --exclude "*draft*"
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-o, --output DIR` | Output directory (default: output) |
| `-d, --depth N` | Recursion depth (default: 0) |
| `-m, --merge` | Merge all PDFs into a single file |
| `--dry-run` | List PDFs without downloading |
| `--delay SECONDS` | Delay between requests (default: 0.5) |
| `--timeout SECONDS` | Request timeout (default: 30) |
| `--user-agent STRING` | Custom User-Agent string |
| `--respect-robots` | Respect robots.txt rules |
| `--progress` | Show progress bars |
| `--include PATTERN` | Include PDFs matching pattern |
| `--exclude PATTERN` | Exclude PDFs matching pattern |
| `--min-size BYTES` | Minimum PDF size |
| `--max-size BYTES` | Maximum PDF size |

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

### With robots.txt Compliance

```python
from fetcharoo import download_pdfs_from_webpage

# Respect robots.txt rules
download_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=2,
    mode='merge',
    write_dir='output',
    respect_robots=True,
    user_agent='MyBot/1.0'
)
```

### Dry-Run Mode

```python
from fetcharoo import download_pdfs_from_webpage

# Preview what would be downloaded
result = download_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=1,
    dry_run=True
)

print(f"Found {result['count']} PDFs:")
for url in result['urls']:
    print(f"  - {url}")
```

### With Progress Bars

```python
from fetcharoo import download_pdfs_from_webpage

# Show progress during download
download_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=2,
    write_dir='output',
    show_progress=True
)
```

### PDF Filtering

```python
from fetcharoo import download_pdfs_from_webpage, FilterConfig

# Filter by filename patterns and size
filter_config = FilterConfig(
    filename_include=['report*.pdf', 'annual*.pdf'],
    filename_exclude=['*draft*', '*temp*'],
    min_size=10000,  # 10KB minimum
    max_size=50000000  # 50MB maximum
)

download_pdfs_from_webpage(
    url='https://example.com',
    recursion_depth=1,
    write_dir='output',
    filter_config=filter_config
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

### Custom User-Agent

```python
from fetcharoo import download_pdfs_from_webpage, set_default_user_agent

# Set a global default User-Agent
set_default_user_agent('MyCompanyBot/1.0 (contact@example.com)')

# Or use per-request User-Agent
download_pdfs_from_webpage(
    url='https://example.com',
    user_agent='SpecificBot/2.0'
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
| `respect_robots` | bool | False | Whether to respect robots.txt |
| `user_agent` | str | None | Custom User-Agent (uses default if None) |
| `dry_run` | bool | False | Preview URLs without downloading |
| `show_progress` | bool | False | Show progress bars |
| `filter_config` | FilterConfig | None | PDF filtering configuration |

### `find_pdfs_from_webpage()`

Find PDF URLs without downloading.

### `process_pdfs()`

Download and save a list of PDF URLs.

### `FilterConfig`

Configuration for PDF filtering:

```python
from fetcharoo import FilterConfig

config = FilterConfig(
    filename_include=['*.pdf'],      # Patterns to include
    filename_exclude=['*draft*'],    # Patterns to exclude
    url_include=['*/reports/*'],     # URL patterns to include
    url_exclude=['*/temp/*'],        # URL patterns to exclude
    min_size=1000,                   # Minimum size in bytes
    max_size=100000000               # Maximum size in bytes
)
```

### Utility Functions

- `merge_pdfs()` - Merge multiple PDF documents
- `is_valid_url()` - Validate URL format and scheme
- `is_safe_domain()` - Check if domain is allowed
- `sanitize_filename()` - Prevent path traversal attacks
- `check_robots_txt()` - Check robots.txt permissions
- `set_default_user_agent()` - Set default User-Agent
- `get_default_user_agent()` - Get current default User-Agent

## Security Features

fetcharoo includes several security measures:

- **Domain restriction**: Limit recursive crawling to specified domains (SSRF protection)
- **Path traversal protection**: Sanitizes filenames to prevent directory escape
- **Rate limiting**: Configurable delays between requests
- **Timeout handling**: Prevents hanging on slow servers
- **URL validation**: Only allows http/https schemes
- **robots.txt compliance**: Optional respect for crawling rules

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
