import logging
import requests
import time
from typing import Optional

# Default User-Agent string - identifies the bot properly for site operators
DEFAULT_USER_AGENT = 'fetcharoo/0.1.0 (+https://github.com/MALathon/fetcharoo)'

# Valid PDF content types
VALID_PDF_CONTENT_TYPES = {
    'application/pdf',
    'application/x-pdf',
    'application/octet-stream',  # Some servers use this for PDFs
}


def _get_default_user_agent() -> str:
    """
    Get the current default User-Agent string from the main module.

    Returns:
        The current default User-Agent string.
    """
    # Import here to avoid circular imports
    from fetcharoo.fetcharoo import get_default_user_agent
    return get_default_user_agent()


def download_pdf(
    pdf_link: str,
    timeout: int = 30,
    max_retries: int = 3,
    user_agent: Optional[str] = None
) -> Optional[bytes]:
    """
    Download a single PDF file from a URL.

    Args:
        pdf_link: The URL of the PDF file to download.
        timeout: Request timeout in seconds. Defaults to 30.
        max_retries: Maximum number of retry attempts. Defaults to 3.
        user_agent: Custom User-Agent string. If None, uses the default.

    Returns:
        The PDF file content as bytes, or None if download failed.
    """
    # Use custom user agent or fall back to default
    if user_agent is None:
        user_agent = _get_default_user_agent()

    headers = {'User-Agent': user_agent}
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
