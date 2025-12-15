import os
import re
import time
import pymupdf
import requests
import logging
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urljoin, urlparse, unquote
from urllib.robotparser import RobotFileParser
from typing import List, Set, Optional, Union, Dict, Callable

from fetcharoo.downloader import download_pdf
from fetcharoo.pdf_utils import merge_pdfs, save_pdf_to_file
from fetcharoo.filtering import FilterConfig, should_download_pdf

# Define constants
DEFAULT_WRITE_DIR = 'output'
DEFAULT_MODE = 'separate'
DEFAULT_TIMEOUT = 30
DEFAULT_REQUEST_DELAY = 0.5  # seconds between requests to avoid hammering servers
MAX_RECURSION_DEPTH = 5  # safety limit

# Default User-Agent string - identifies the bot properly for site operators
DEFAULT_USER_AGENT = 'fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)'

# Module-level variable to track the current default user agent
_default_user_agent = DEFAULT_USER_AGENT

# Configure logging
logging.basicConfig(level=logging.INFO)

# Cache for robots.txt parsers per domain
_robots_cache: Dict[str, RobotFileParser] = {}

# Valid sort_by options
SORT_BY_OPTIONS = ('none', 'numeric', 'alpha', 'alpha_desc')


def _extract_numeric_key(url: str) -> tuple:
    """
    Extract numeric parts from a URL for sorting.

    Returns a tuple of numbers found in the filename, allowing proper
    sorting of files like 'chapter_1.pdf', 'chapter_2.pdf', 'chapter_10.pdf'.
    """
    filename = os.path.basename(urlparse(url).path)
    # Find all numeric sequences in the filename
    numbers = re.findall(r'\d+', filename)
    # Convert to integers for proper numeric sorting
    return tuple(int(n) for n in numbers) if numbers else (float('inf'),)


def _get_sort_key(sort_by: Optional[str], sort_key: Optional[Callable[[str], any]]) -> Optional[Callable[[str], any]]:
    """
    Get the appropriate sort key function based on parameters.

    Args:
        sort_by: Built-in sort strategy ('numeric', 'alpha', 'alpha_desc', 'none')
        sort_key: Custom sort key function

    Returns:
        A sort key function or None if no sorting should be applied.
    """
    # Custom sort_key takes precedence
    if sort_key is not None:
        return sort_key

    if sort_by is None or sort_by == 'none':
        return None

    if sort_by == 'numeric':
        return _extract_numeric_key
    elif sort_by == 'alpha':
        return lambda url: os.path.basename(urlparse(url).path).lower()
    elif sort_by == 'alpha_desc':
        # For descending, we'll handle it in the sort call
        return lambda url: os.path.basename(urlparse(url).path).lower()
    else:
        logging.warning(f"Unknown sort_by value: {sort_by}. Using no sorting.")
        return None


def set_default_user_agent(agent_string: str) -> None:
    """
    Set the default User-Agent string for all HTTP requests.

    Args:
        agent_string: The User-Agent string to use as default.
    """
    global _default_user_agent
    _default_user_agent = agent_string


def get_default_user_agent() -> str:
    """
    Get the current default User-Agent string.

    Returns:
        The current default User-Agent string.
    """
    return _default_user_agent


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


def check_robots_txt(url: str, user_agent: str = 'fetcharoo-bot') -> bool:
    """
    Check if crawling a URL is allowed according to robots.txt.

    This function fetches and parses the robots.txt file for the domain
    and checks if the given URL can be fetched by the specified user agent.
    Results are cached per domain to avoid repeated fetches.

    Args:
        url: The URL to check.
        user_agent: The user agent string to check permissions for. Defaults to 'fetcharoo-bot'.

    Returns:
        True if crawling is allowed, False if disallowed.
        Returns True if robots.txt is missing or cannot be fetched (permissive default).
    """
    try:
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        robots_url = f"{domain}/robots.txt"

        # Check if we have a cached parser for this domain
        if domain in _robots_cache:
            rp = _robots_cache[domain]
        else:
            # Create a new RobotFileParser
            rp = RobotFileParser()
            rp.set_url(robots_url)

            try:
                # Fetch robots.txt using requests library
                headers = {'User-Agent': user_agent}
                response = requests.get(robots_url, headers=headers, timeout=10)

                if response.status_code == 200:
                    # Parse the robots.txt content
                    robots_content = response.text.splitlines()
                    rp.parse(robots_content)
                else:
                    # If robots.txt doesn't exist (404 or other error), allow everything
                    logging.debug(f"robots.txt returned status {response.status_code} for {domain}")
                    rp.parse([])

                # Cache the parser
                _robots_cache[domain] = rp

            except requests.exceptions.RequestException as e:
                # If we can't fetch robots.txt, assume it's allowed (permissive default)
                logging.debug(f"Could not fetch robots.txt for {domain}: {e}")
                # Cache a permissive parser
                rp = RobotFileParser()
                rp.set_url(robots_url)
                # An empty robots.txt allows everything
                rp.parse([])
                _robots_cache[domain] = rp

        # Check if the URL can be fetched
        can_fetch = rp.can_fetch(user_agent, url)
        return can_fetch

    except Exception as e:
        # On any error, default to allowing (permissive)
        logging.debug(f"Error checking robots.txt for {url}: {e}")
        return True


def find_pdfs_from_webpage(
    url: str,
    recursion_depth: int = 0,
    visited: Optional[Set[str]] = None,
    allowed_domains: Optional[Set[str]] = None,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    timeout: int = DEFAULT_TIMEOUT,
    respect_robots: bool = False,
    user_agent: Optional[str] = None,
    show_progress: bool = False,
    deduplicate: bool = True,
    _seen_pdfs: Optional[Set[str]] = None
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
        respect_robots: Whether to respect robots.txt rules. Defaults to False.
        user_agent: Custom User-Agent string. If None, uses the default.
        show_progress: Whether to show progress bars. Defaults to False.
        deduplicate: Whether to remove duplicate PDF URLs. Defaults to True.
                    When True, each unique PDF URL appears only once in the result.
        _seen_pdfs: Internal parameter for tracking seen PDFs during recursion.

    Returns:
        A list of PDF URLs found on the webpage (deduplicated by default).
    """
    # Safety limit on recursion depth
    if recursion_depth > MAX_RECURSION_DEPTH:
        logging.warning(f"Recursion depth {recursion_depth} exceeds maximum {MAX_RECURSION_DEPTH}, limiting.")
        recursion_depth = MAX_RECURSION_DEPTH

    if visited is None:
        visited = set()

    # Initialize seen PDFs set for deduplication
    if deduplicate and _seen_pdfs is None:
        _seen_pdfs = set()

    # Initialize allowed domains from the base URL if not provided
    if allowed_domains is None:
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc.lower().split(':')[0]
        allowed_domains = {base_domain}

    # Use custom user agent or fall back to default
    if user_agent is None:
        user_agent = get_default_user_agent()

    visited.add(url)
    pdf_links = []

    # Log progress if enabled
    if show_progress:
        logging.info(f"Finding PDFs from: {url}")

    try:
        if not is_valid_url(url):
            logging.error(f"Invalid URL: {url}")
            return pdf_links

        if not is_safe_domain(url, allowed_domains):
            logging.warning(f"URL domain not in allowed list: {url}")
            return pdf_links

        # Fetch the webpage content with timeout
        headers = {'User-Agent': user_agent}
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
                # Check robots.txt compliance if enabled
                if respect_robots and not check_robots_txt(link, user_agent):
                    logging.warning(f"URL disallowed by robots.txt: {link}")
                    continue

                # Deduplicate: check both local list and global seen set
                is_duplicate = link in pdf_links
                if deduplicate and _seen_pdfs is not None:
                    is_duplicate = is_duplicate or link in _seen_pdfs

                if not is_duplicate:
                    pdf_links.append(link)
                    if deduplicate and _seen_pdfs is not None:
                        _seen_pdfs.add(link)
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
                        timeout,
                        respect_robots,
                        user_agent,
                        show_progress,
                        deduplicate,
                        _seen_pdfs
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
    user_agent: Optional[str] = None,
    show_progress: bool = False,
    filter_config: Optional[FilterConfig] = None,
    sort_by: Optional[str] = None,
    sort_key: Optional[Callable[[str], any]] = None,
    output_name: Optional[str] = None
) -> bool:
    """
    Download and process each PDF file based on the specified mode ('separate' or 'merge').
    Returns True if at least one PDF was processed successfully, False otherwise.

    Args:
        pdf_links: A list of PDF URLs to process.
        write_dir: The directory to write the output PDF files. Defaults to DEFAULT_WRITE_DIR.
        mode: The processing mode, either 'separate' or 'merge'. Defaults to DEFAULT_MODE.
        timeout: The timeout for downloading PDFs in seconds. Defaults to 30.
        user_agent: Custom User-Agent string. If None, uses the default.
        show_progress: Whether to show progress bars. Defaults to False.
        filter_config: Optional FilterConfig to filter PDFs. If None, no filtering is applied.
        sort_by: Built-in sort strategy for merge mode: 'numeric', 'alpha', 'alpha_desc', or 'none'.
                 'numeric' sorts by numbers in filename (e.g., chapter_1, chapter_2, chapter_10).
                 'alpha' sorts alphabetically by filename.
                 'alpha_desc' sorts alphabetically descending.
                 Defaults to None (no sorting, preserves discovery order).
        sort_key: Custom sort key function that takes a URL and returns a sortable value.
                  Takes precedence over sort_by if both are provided.
        output_name: Custom filename for merged PDF output. Only used in 'merge' mode.
                    Defaults to 'merged.pdf' if not specified.

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

    # Apply sorting if requested (useful for merge mode to ensure correct order)
    resolved_sort_key = _get_sort_key(sort_by, sort_key)
    if resolved_sort_key is not None:
        reverse = (sort_by == 'alpha_desc')
        pdf_links = sorted(pdf_links, key=resolved_sort_key, reverse=reverse)
        logging.debug(f"Sorted {len(pdf_links)} PDFs using {'custom key' if sort_key else sort_by}")

    # Validate mode
    if mode not in ('separate', 'merge'):
        logging.error(f"Invalid mode: {mode}. Must be 'separate' or 'merge'.")
        return False

    # Sanitize and validate the write directory
    write_dir = os.path.abspath(write_dir)

    # Ensure the write directory exists
    os.makedirs(write_dir, exist_ok=True)

    # Use custom user agent or fall back to default
    if user_agent is None:
        user_agent = get_default_user_agent()

    # Download PDF contents with optional progress bar
    if show_progress:
        pdf_contents = [download_pdf(pdf_link, timeout, user_agent=user_agent) for pdf_link in tqdm(pdf_links, desc="Downloading PDFs")]
    else:
        pdf_contents = [download_pdf(pdf_link, timeout, user_agent=user_agent) for pdf_link in pdf_links]

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
            if output_name:
                # Sanitize custom filename and ensure .pdf extension
                file_name = sanitize_filename(output_name)
            else:
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
    respect_robots: bool = False,
    user_agent: Optional[str] = None,
    dry_run: bool = False,
    show_progress: bool = False,
    filter_config: Optional[FilterConfig] = None,
    sort_by: Optional[str] = None,
    sort_key: Optional[Callable[[str], any]] = None,
    output_name: Optional[str] = None
) -> Union[bool, Dict[str, Union[List[str], int]]]:
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
        respect_robots: Whether to respect robots.txt rules. Defaults to False.
        user_agent: Custom User-Agent string. If None, uses the default.
        dry_run: If True, find and return PDF URLs without downloading them. Defaults to False.
        show_progress: Whether to show progress bars. Defaults to False.
        filter_config: Optional FilterConfig to filter PDFs. If None, no filtering is applied.
        sort_by: Built-in sort strategy for merge mode: 'numeric', 'alpha', 'alpha_desc', or 'none'.
                 Defaults to None (no sorting, preserves discovery order).
        sort_key: Custom sort key function that takes a URL and returns a sortable value.
                  Takes precedence over sort_by if both are provided.
        output_name: Custom filename for merged PDF output. Only used in 'merge' mode.
                    Defaults to 'merged.pdf' if not specified.

    Returns:
        If dry_run=True: A dict with {"urls": [...], "count": N}
        If dry_run=False: True if at least one PDF was processed successfully, False otherwise.
    """
    # Find PDF links from the webpage
    pdf_links = find_pdfs_from_webpage(
        url,
        recursion_depth,
        allowed_domains=allowed_domains,
        request_delay=request_delay,
        timeout=timeout,
        respect_robots=respect_robots,
        user_agent=user_agent,
        show_progress=show_progress
    )

    # If dry_run mode, return the URLs without downloading
    if dry_run:
        # Apply filename/URL filtering if filter_config is provided
        if filter_config is not None:
            filtered_links = []
            for pdf_link in pdf_links:
                if should_download_pdf(pdf_link, size_bytes=None, filter_config=filter_config):
                    filtered_links.append(pdf_link)
                else:
                    logging.info(f"DRY RUN: Filtered out PDF: {pdf_link}")
            pdf_links = filtered_links

        logging.info(f"DRY RUN: Found {len(pdf_links)} PDF(s) that would be downloaded:")
        for pdf_url in pdf_links:
            logging.info(f"  - {pdf_url}")
        return {
            "urls": pdf_links,
            "count": len(pdf_links)
        }

    # Process the PDFs based on the specified mode
    return process_pdfs(
        pdf_links,
        write_dir=write_dir,
        mode=mode,
        timeout=timeout,
        user_agent=user_agent,
        show_progress=show_progress,
        filter_config=filter_config,
        sort_by=sort_by,
        sort_key=sort_key,
        output_name=output_name
    )
