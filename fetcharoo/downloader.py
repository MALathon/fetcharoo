import logging
import requests
import time

def download_pdf(pdf_link, timeout=10, max_retries=3) -> bytes | None:
    """Download a single PDF file from a URL."""
    start_time = time.time()
    for _ in range(max_retries):
        try:
            response = requests.get(pdf_link, timeout=timeout)
            response.raise_for_status()
            if response.headers['Content-Type'] != 'application/pdf':
                logging.error(f'The file is not a PDF file: {pdf_link}')
                return None
            return response.content
        except requests.exceptions.RequestException as e:
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                logging.error(f'Failed to fetch the PDF file after {timeout} seconds: {e}')
                return None
            # Delay before retrying
            time.sleep(1)  # Sleep for 1 second before retrying
    logging.error(f'Failed to fetch the PDF file after {max_retries} retries: {pdf_link}')
    return None
