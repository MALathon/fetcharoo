# PDF Filtering Examples

This document provides examples of using the PDF filtering feature in fetcharoo.

Author: Mark A. Lifson, Ph.D.

## Overview

The filtering feature allows you to filter which PDFs to download based on:
1. **Filename patterns** - include/exclude patterns using wildcards
2. **File size limits** - minimum and maximum file size
3. **URL patterns** - include/exclude URL patterns

## Basic Usage

### Import the FilterConfig

```python
from fetcharoo import download_pdfs_from_webpage, FilterConfig
```

### Example 1: Filter by Filename Pattern

Download only files matching "report*.pdf":

```python
from fetcharoo import download_pdfs_from_webpage, FilterConfig

# Create filter configuration
filter_config = FilterConfig(
    filename_include=['report*.pdf']
)

# Download PDFs with filtering
download_pdfs_from_webpage(
    url='https://example.com',
    write_dir='output',
    mode='separate',
    filter_config=filter_config
)
```

### Example 2: Exclude Draft Files

Download all PDFs except drafts:

```python
filter_config = FilterConfig(
    filename_include=['*.pdf'],
    filename_exclude=['*draft*', '*temp*', '*preliminary*']
)

download_pdfs_from_webpage(
    url='https://example.com',
    filter_config=filter_config
)
```

### Example 3: Filter by File Size

Download only PDFs between 1MB and 10MB:

```python
filter_config = FilterConfig(
    min_size=1_000_000,   # 1MB minimum
    max_size=10_000_000   # 10MB maximum
)

download_pdfs_from_webpage(
    url='https://example.com',
    filter_config=filter_config
)
```

### Example 4: Filter by URL Pattern

Download only PDFs from specific paths:

```python
filter_config = FilterConfig(
    url_include=['*/publications/*', '*/reports/*'],
    url_exclude=['*/archive/*', '*/old/*']
)

download_pdfs_from_webpage(
    url='https://example.com',
    filter_config=filter_config
)
```

### Example 5: Combined Filters

Combine multiple filters for precise control:

```python
filter_config = FilterConfig(
    # Filename filters
    filename_include=['*annual*report*.pdf', '*quarterly*report*.pdf'],
    filename_exclude=['*draft*', '*preliminary*'],

    # Size filters
    min_size=100_000,      # At least 100KB
    max_size=50_000_000,   # At most 50MB

    # URL filters
    url_include=['https://trusted-source.org/publications/*'],
    url_exclude=['*/drafts/*', '*/temp/*']
)

download_pdfs_from_webpage(
    url='https://trusted-source.org',
    recursion_depth=1,
    filter_config=filter_config
)
```

## Pattern Syntax

The filtering uses `fnmatch` pattern matching (case-insensitive):

- `*` - Matches everything
- `?` - Matches any single character
- `[seq]` - Matches any character in seq
- `[!seq]` - Matches any character not in seq

### Pattern Examples

```python
# Match any PDF
'*.pdf'

# Match reports with any suffix
'report*.pdf'

# Match specific year
'*2023*.pdf'

# Match single character
'report?.pdf'  # Matches report1.pdf, reportA.pdf, etc.

# Match character range
'report[0-9].pdf'  # Matches report0.pdf through report9.pdf
```

## Real-World Scenarios

### Scenario 1: Download Annual Financial Reports

```python
from fetcharoo import download_pdfs_from_webpage, FilterConfig

# Download only annual reports, excluding drafts
filter_config = FilterConfig(
    filename_include=['*annual*report*.pdf', '*yearly*report*.pdf'],
    filename_exclude=['*draft*', '*preliminary*', '*unaudited*'],
    min_size=50_000,  # Reports should be at least 50KB
    max_size=20_000_000  # But not larger than 20MB
)

download_pdfs_from_webpage(
    url='https://company.com/investor-relations',
    recursion_depth=1,
    mode='separate',
    write_dir='annual_reports',
    filter_config=filter_config
)
```

### Scenario 2: Download Research Papers from Specific Journal

```python
filter_config = FilterConfig(
    # Only from specific journal sections
    url_include=['https://journal.org/articles/*', 'https://journal.org/papers/*'],
    url_exclude=['https://journal.org/articles/retracted/*'],

    # Typical research paper size range
    min_size=200_000,  # At least 200KB
    max_size=10_000_000,  # At most 10MB

    # Exclude supplementary materials
    filename_exclude=['*supplement*', '*appendix*', '*supporting*']
)

download_pdfs_from_webpage(
    url='https://journal.org',
    recursion_depth=2,
    filter_config=filter_config
)
```

### Scenario 3: Download Presentations Within Size Range

```python
# Presentations are typically 1-5 MB
filter_config = FilterConfig(
    filename_include=['*presentation*.pdf', '*slides*.pdf', '*deck*.pdf'],
    min_size=1_000_000,  # 1MB minimum
    max_size=5_000_000,  # 5MB maximum
)

download_pdfs_from_webpage(
    url='https://conference.com/presentations',
    filter_config=filter_config
)
```

## Advanced Usage

### Using with process_pdfs Directly

If you already have a list of PDF URLs, you can use `process_pdfs` with filtering:

```python
from fetcharoo import process_pdfs, FilterConfig

pdf_urls = [
    'https://example.com/report1.pdf',
    'https://example.com/report2.pdf',
    'https://example.com/draft_report.pdf',
]

filter_config = FilterConfig(
    filename_exclude=['*draft*']
)

process_pdfs(
    pdf_links=pdf_urls,
    write_dir='output',
    mode='separate',
    filter_config=filter_config
)
# Only report1.pdf and report2.pdf will be downloaded
```

### Checking if a PDF Should Be Downloaded

You can use the `should_download_pdf` function to check if a specific PDF passes filters:

```python
from fetcharoo import should_download_pdf, FilterConfig

filter_config = FilterConfig(
    filename_include=['report*.pdf'],
    min_size=1000,
    max_size=100000
)

# Check if a PDF passes filters
url = 'https://example.com/report_2023.pdf'
size = 5000

if should_download_pdf(url, size, filter_config):
    print(f"PDF {url} passes all filters")
else:
    print(f"PDF {url} is filtered out")
```

## Filter Behavior

### Include vs Exclude

- **Empty include list**: All items match (unless excluded)
- **Non-empty include list**: Only items matching at least one pattern are included
- **Exclude always overrides include**: If an item matches any exclude pattern, it's rejected even if it matches an include pattern

### Size Filtering

- If size is `None` (unknown), size filters are skipped
- Size filters are applied after download (when actual size is known)
- Both filename and URL filters are applied before download (to avoid unnecessary downloads)

### Multiple Patterns

All patterns within a category are OR'd together:
- An item matches if it matches ANY include pattern
- An item is excluded if it matches ANY exclude pattern

## Tips and Best Practices

1. **Start broad, then narrow**: Use include patterns to broadly select, then use exclude patterns to remove unwanted items

2. **Size filtering optimization**: Size filters are checked after download. If you want to avoid downloading large files, use URL/filename patterns as a pre-filter.

3. **Test your patterns**: Use the demonstration script or unit tests to verify your patterns match what you expect

4. **Case-insensitive**: All pattern matching is case-insensitive, so `Report.PDF` matches `report*.pdf`

5. **Combine filters**: Don't hesitate to combine multiple filter types for precise control

## Troubleshooting

### No PDFs Downloaded

If no PDFs are downloaded:

1. Check that your include patterns are not too restrictive
2. Verify exclude patterns aren't blocking everything
3. Check size limits are appropriate
4. Enable logging to see which PDFs are being filtered:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

### Too Many PDFs Downloaded

If too many PDFs are downloaded:

1. Add more specific include patterns
2. Add exclude patterns for unwanted files
3. Set appropriate size limits
4. Use URL patterns to restrict to specific paths

## See Also

- Main README for general fetcharoo usage
- `tests/test_filtering.py` for comprehensive test examples
- `test_filtering_demo.py` for runnable demonstrations
