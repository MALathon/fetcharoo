import os
import re
import time
import pymupdf
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from typing import List, Set, Optional

from fetcharoo.downloader import download_pdf
from fetcharoo.pdf_utils import merge_pdfs, save_pdf_to_file
from fetcharoo.filtering import FilterConfig, should_download_pdf

# Define constants
DEFAULT_WRITE_DIR = 'output'
DEFAULT_MODE = 'separate'
DEFAULT_TIMEOUT = 30
DEFAULT_REQUEST_DELAY = 0.5  # seconds between requests to avoid hammering servers
MAX_RECURSION_DEPTH = 5  # safety limit

# Modern User-Agent string
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Configure logging
logging.basicConfig(level=logging.INFO)


def is_valid_url(url: str) -> bool:
    """Check if a URL is valid and uses a safe scheme."""
    try:
        parsed_url = urlparse(url)
        # Only allow http and https schemes
        if parsed_url.scheme not in ('http', 'https'):
            return False
        return bool(parsed_url.netloc)
    except ValueError:
        return False


def is_safe_domain(url: str, allowed_domains: Optional[Set[str]] = None) -> bool:
    """
    Check if a URL's domain is in the allowed list.

    Args:
        url: The URL to check.
        allowed_domains: Set of allowed domain names. If None, all domains are allowed.

    Returns:
        True if the domain is allowed, False otherwise.
    """
    if allowed_domains is None:
        return True

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        # Strip port if present
        domain = domain.split(':')[0]

        # Check if domain matches any allowed domain (including subdomains)
        for allowed in allowed_domains:
            allowed = allowed.lower()
            if domain == allowed or domain.endswith('.' + allowed):
                return True
        return False
    except ValueError:
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.

    Args:
        filename: The filename to sanitize.

    Returns:
        A safe filename with path traversal characters removed.
    """
    # URL decode the filename
    filename = unquote(filename)

    # Get only the base name (remove any path components)
    filename = os.path.basename(filename)

    # Remove any remaining path separators
    filename = filename.replace('/', '').replace('\\', '')

    # Remove null bytes and other dangerous characters
    filename = filename.replace('\x00', '')

    # Remove leading dots (hidden files on Unix)
    filename = filename.lstrip('.')

    # Replace potentially dangerous characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)

    # Ensure filename is not empty after sanitization
    if not filename or filename == '.pdf':
        filename = 'downloaded.pdf'

    # Ensure it ends with .pdf
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'

    # Limit filename length
    max_length = 200
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext

    return filename


def find_pdfs_from_webpage(
    url: str,
    recursion_depth: int = 0,
    visited: Optional[Set[str]] = None,
    allowed_domains: Optional[Set[str]] = None,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    timeout: int = DEFAULT_TIMEOUT
) -> List[str]:
    """
    Find and return a list of PDF URLs from a webpage up to a specified recursion depth.

    Args:
        url: The URL of the webpage to search for PDFs.
        recursion_depth: The maximum depth of recursion for linked webpages. Defaults to 0.
        visited: A set of visited URLs to avoid cyclic loops. Defaults to None.
        allowed_domains: Set of allowed domain names for recursive crawling.
                        If None, only the initial URL's domain is allowed.
        request_delay: Delay in seconds between requests. Defaults to 0.5.
        timeout: Request timeout in seconds. Defaults to 30.

    Returns:
        A list of PDF URLs found on the webpage.
    """
    # Safety limit on recursion depth
    if recursion_depth > MAX_RECURSION_DEPTH:
        logging.warning(f"Recursion depth {recursion_depth} exceeds maximum {MAX_RECURSION_DEPTH}, limiting.")
        recursion_depth = MAX_RECURSION_DEPTH

    if visited is None:
        visited = set()

    # Initialize allowed domains from the base URL if not provided
    if allowed_domains is None:
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc.lower().split(':')[0]
        allowed_domains = {base_domain}

    visited.add(url)
    pdf_links = []

    try:
        if not is_valid_url(url):
            logging.error(f"Invalid URL: {url}")
            return pdf_links

        if not is_safe_domain(url, allowed_domains):
            logging.warning(f"URL domain not in allowed list: {url}")
            return pdf_links

        # Fetch the webpage content with timeout
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all anchor tags with href attributes
        anchors = soup.find_all('a', href=True)

        # Extract PDF links and other links for recursive search
        other_links = []
        for anchor in anchors:
            link = urljoin(url, anchor['href'])

            if not is_valid_url(link):
                continue

            if link.lower().endswith('.pdf'):
                if link not in pdf_links:  # Avoid duplicates
                    pdf_links.append(link)
            elif recursion_depth > 0:
                if is_safe_domain(link, allowed_domains):
                    other_links.append(link)

        # Recursively search for PDF links on linked webpages
        if recursion_depth > 0:
            for link in other_links:
                if link not in visited:
                    # Rate limiting: delay between requests
                    time.sleep(request_delay)
                    pdf_links.extend(find_pdfs_from_webpage(
                        link,
                        recursion_depth - 1,
                        visited,
                        allowed_domains,
                        request_delay,
                        timeout
                    ))

    except requests.exceptions.Timeout:
        logging.error(f"Request timed out: {url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching webpage: {e}")

    return pdf_links


def process_pdfs(
    pdf_links: List[str],
    write_dir: str = DEFAULT_WRITE_DIR,
    mode: str = DEFAULT_MODE,
    timeout: int = DEFAULT_TIMEOUT,
    filter_config: Optional[FilterConfig] = None
) -> bool:
    """
    Download and process each PDF file based on the specified mode ('separate' or 'merge').
    Returns True if at least one PDF was processed successfully, False otherwise.

    Args:
        pdf_links: A list of PDF URLs to process.
        write_dir: The directory to write the output PDF files. Defaults to DEFAULT_WRITE_DIR.
        mode: The processing mode, either 'separate' or 'merge'. Defaults to DEFAULT_MODE.
        timeout: The timeout for downloading PDFs in seconds. Defaults to 30.
        filter_config: Optional FilterConfig to filter PDFs. If None, no filtering is applied.

    Returns:
        True if at least one PDF was processed successfully, False otherwise.
    """
    if not pdf_links:
        return False

    # Apply filtering if filter_config is provided
    if filter_config is not None:
        filtered_links = []
        for pdf_link in pdf_links:
            # For now, we don't have size information until we download
            # So we only apply filename and URL filters here
            if should_download_pdf(pdf_link, size_bytes=None, filter_config=filter_config):
                filtered_links.append(pdf_link)
            else:
                logging.info(f"Filtered out PDF (filename/URL): {pdf_link}")
        pdf_links = filtered_links

        if not pdf_links:
            logging.warning("All PDFs were filtered out.")
            return False

    # Validate mode
    if mode not in ('separate', 'merge'):
        logging.error(f"Invalid mode: {mode}. Must be 'separate' or 'merge'.")
        return False

    # Sanitize and validate the write directory
    write_dir = os.path.abspath(write_dir)

    # Ensure the write directory exists
    os.makedirs(write_dir, exist_ok=True)

    # Download PDF contents
    pdf_contents = [download_pdf(pdf_link, timeout) for pdf_link in pdf_links]
    pdf_contents_valid = [(content, link) for content, link in zip(pdf_contents, pdf_links)
                          if content is not None and content.startswith(b'%PDF')]

    if not pdf_contents_valid:
        logging.warning("No valid PDF content found.")
        return False

    # Apply size filtering if filter_config is provided
    if filter_config is not None and (filter_config.min_size is not None or filter_config.max_size is not None):
        size_filtered = []
        for content, link in pdf_contents_valid:
            size_bytes = len(content)
            if should_download_pdf(link, size_bytes=size_bytes, filter_config=filter_config):
                size_filtered.append((content, link))
            else:
                logging.info(f"Filtered out PDF (size: {size_bytes} bytes): {link}")
        pdf_contents_valid = size_filtered

        if not pdf_contents_valid:
            logging.warning("All PDFs were filtered out by size limits.")
            return False

    success = False
    try:
        if mode == 'merge':
            # Determine the output file name for the merged PDF
            file_name = 'merged.pdf'
            output_file_path = os.path.join(write_dir, file_name)

            # Merge PDFs and save the merged document
            merged_pdf = merge_pdfs([content for content, _ in pdf_contents_valid])
            save_pdf_to_file(merged_pdf, output_file_path, mode='append')
            success = True

        elif mode == 'separate':
            # Save each PDF as a separate file
            for pdf_content, pdf_link in pdf_contents_valid:
                # Sanitize the filename to prevent path traversal
                file_name = sanitize_filename(os.path.basename(urlparse(pdf_link).path))
                output_file_path = os.path.join(write_dir, file_name)

                # Handle file name collision
                counter = 1
                base_name = os.path.splitext(file_name)[0]
                while os.path.exists(output_file_path):
                    file_name = f"{base_name}_{counter}.pdf"
                    output_file_path = os.path.join(write_dir, file_name)
                    counter += 1

                # Create a new PDF document from the content
                pdf_document = pymupdf.Document(stream=pdf_content, filetype="pdf")
                save_pdf_to_file(pdf_document, output_file_path, mode='overwrite')
                success = True

    except Exception as e:
        logging.error(f"Error processing PDFs: {e}")

    return success


def download_pdfs_from_webpage(
    url: str,
    recursion_depth: int = 0,
    mode: str = DEFAULT_MODE,
    write_dir: str = DEFAULT_WRITE_DIR,
    allowed_domains: Optional[Set[str]] = None,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    timeout: int = DEFAULT_TIMEOUT,
    filter_config: Optional[FilterConfig] = None
) -> bool:
    """
    Download PDFs from a webpage and process them based on the specified mode.

    Args:
        url: The URL of the webpage to search for PDFs.
        recursion_depth: The maximum depth of recursion for linked webpages. Defaults to 0.
        mode: The processing mode, either 'separate' or 'merge'. Defaults to DEFAULT_MODE.
        write_dir: The directory to write the output PDF files. Defaults to DEFAULT_WRITE_DIR.
        allowed_domains: Set of allowed domain names for recursive crawling.
                        If None, only the initial URL's domain is allowed.
        request_delay: Delay in seconds between requests. Defaults to 0.5.
        timeout: Request timeout in seconds. Defaults to 30.
        filter_config: Optional FilterConfig to filter PDFs. If None, no filtering is applied.

    Returns:
        True if at least one PDF was processed successfully, False otherwise.
    """
    # Find PDF links from the webpage
    pdf_links = find_pdfs_from_webpage(
        url,
        recursion_depth,
        allowed_domains=allowed_domains,
        request_delay=request_delay,
        timeout=timeout
    )

    # Process the PDFs based on the specified mode
    return process_pdfs(pdf_links, write_dir, mode, timeout, filter_config)
