import logging
import requests
import time
from typing import Optional

# Modern User-Agent string
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Valid PDF content types
VALID_PDF_CONTENT_TYPES = {
    'application/pdf',
    'application/x-pdf',
    'application/octet-stream',  # Some servers use this for PDFs
}


def download_pdf(
    pdf_link: str,
    timeout: int = 30,
    max_retries: int = 3
) -> Optional[bytes]:
    """
    Download a single PDF file from a URL.

    Args:
        pdf_link: The URL of the PDF file to download.
        timeout: Request timeout in seconds. Defaults to 30.
        max_retries: Maximum number of retry attempts. Defaults to 3.

    Returns:
        The PDF file content as bytes, or None if download failed.
    """
    headers = {'User-Agent': USER_AGENT}
    start_time = time.time()

    for attempt in range(max_retries):
        try:
            response = requests.get(pdf_link, headers=headers, timeout=timeout)
            response.raise_for_status()

            # Check content type (be flexible as some servers misconfigure this)
            content_type = response.headers.get('Content-Type', '').lower().split(';')[0].strip()

            # Accept valid PDF content types or verify by magic bytes
            if content_type not in VALID_PDF_CONTENT_TYPES:
                # Check for PDF magic bytes as fallback
                if not response.content.startswith(b'%PDF'):
                    logging.warning(f'Content-Type "{content_type}" is not PDF and magic bytes check failed: {pdf_link}')
                    return None

            return response.content

        except requests.exceptions.Timeout:
            logging.warning(f'Request timed out (attempt {attempt + 1}/{max_retries}): {pdf_link}')
        except requests.exceptions.RequestException as e:
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout * max_retries:
                logging.error(f'Failed to fetch the PDF file after {elapsed_time:.1f} seconds: {e}')
                return None
            logging.warning(f'Request failed (attempt {attempt + 1}/{max_retries}): {e}')

        # Exponential backoff before retrying
        if attempt < max_retries - 1:
            sleep_time = min(2 ** attempt, 10)  # Cap at 10 seconds
            time.sleep(sleep_time)

    logging.error(f'Failed to fetch the PDF file after {max_retries} retries: {pdf_link}')
    return None
