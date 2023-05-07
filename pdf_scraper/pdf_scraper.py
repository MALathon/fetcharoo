import os
import fitz
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Set, Optional
from pdf_scraper.downloader import download_pdf
from pdf_scraper.pdf_utils import merge_pdfs, save_pdf_to_file

# Define constants
DEFAULT_WRITE_DIR = 'output'
DEFAULT_MODE = 'separate'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'

# Configure logging
logging.basicConfig(level=logging.INFO)

def is_valid_url(url: str) -> bool:
    """Check if a URL is valid."""
    try:
        parsed_url = urlparse(url)
        return bool(parsed_url.scheme) and bool(parsed_url.netloc)
    except ValueError:
        return False

def find_pdfs_from_webpage(url: str, recursion_depth: int = 0, visited: Optional[Set[str]] = None) -> List[str]:
    """
    Find and return a list of PDF URLs from a webpage up to a specified recursion depth.
    
    Args:
        url (str): The URL of the webpage to search for PDFs.
        recursion_depth (int, optional): The maximum depth of recursion for linked webpages. Defaults to 0.
        visited (Optional[Set[str]], optional): A set of visited URLs to avoid cyclic loops. Defaults to None.
    
    Returns:
        List[str]: A list of PDF URLs found on the webpage.
    """

    if visited is None:
        visited = set()
    visited.add(url)
    
    pdf_links = []

    try:
        if not is_valid_url(url):
            logging.error(f"Invalid URL: {url}")
            return pdf_links
        # Fetch the webpage content
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all anchor tags with href attributes
        anchors = soup.find_all('a', href=True)

        # Extract PDF links and other links for recursive search
        other_links = []
        for anchor in anchors:
            link = urljoin(url, anchor['href'])
            if link.lower().endswith('.pdf'):
                pdf_links.append(link)
            elif recursion_depth > 0:
                parsed_link = urlparse(link)
                if parsed_link.scheme in ('http', 'https'):
                    other_links.append(link)

        # Recursively search for PDF links on linked webpages
        if recursion_depth > 0:
            for link in other_links:
                if link not in visited:
                    pdf_links.extend(find_pdfs_from_webpage(link, recursion_depth - 1, visited))

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching webpage: {e}")

    return pdf_links

def process_pdfs(pdf_links: List[str], write_dir: str = DEFAULT_WRITE_DIR, mode: str = DEFAULT_MODE, timeout: int = 10) -> bool:
    """
    Download and process each PDF file based on the specified mode ('separate' or 'merge').
    Returns True if at least one PDF was processed successfully, False otherwise.
    
    Args:
        pdf_links (List[str]): A list of PDF URLs to process.
        write_dir (str, optional): The directory to write the output PDF files. Defaults to DEFAULT_WRITE_DIR.
        mode (str, optional): The processing mode, either 'separate' or 'merge'. Defaults to DEFAULT_MODE.
        timeout (int, optional): The timeout for downloading PDFs in seconds. Defaults to 10.
    
    Returns:
        bool: True if at least one PDF was processed successfully, False otherwise.
    """
    if not pdf_links:
        return False

    # Ensure the write directory exists
    os.makedirs(write_dir, exist_ok=True)
    
    # Download PDF contents
    pdf_contents = [download_pdf(pdf_link, timeout) for pdf_link in pdf_links]
    pdf_contents = [content for content in pdf_contents if content is not None and content.startswith(b'%PDF')]

    success = False
    try:
        if mode == 'merge':
            # Determine the output file name for the merged PDF
            file_name = 'merged.pdf'
            output_file_path = os.path.join(write_dir, file_name)

            # Merge PDFs and save the merged document
            merged_pdf = merge_pdfs(pdf_contents)
            save_pdf_to_file(merged_pdf, output_file_path, mode='append')
            success = True

        elif mode == 'separate':
            # Save each PDF as a separate file
            for pdf_content, pdf_link in zip(pdf_contents, pdf_links):
                # Determine the output file name for each PDF
                file_name = os.path.basename(pdf_link)
                output_file_path = os.path.join(write_dir, file_name)

                # Handle file name collision
                counter = 1
                while os.path.exists(output_file_path):
                    file_name = f"{os.path.splitext(os.path.basename(pdf_link))[0]}_{counter}.pdf"
                    output_file_path = os.path.join(write_dir, file_name)
                    counter += 1

                # Create a new PDF document from the content
                pdf_document = fitz.Document(stream=pdf_content, filetype="pdf")
                save_pdf_to_file(pdf_document, output_file_path, mode='overwrite')
                success = True
    except Exception as e:
        logging.error(f"Error processing PDFs: {e}")


    return success

def download_pdfs_from_webpage(url: str, recursion_depth: int = 0, mode: str = DEFAULT_MODE, write_dir: str = DEFAULT_WRITE_DIR) -> None:
    """
    Download PDFs from a webpage and process them based on the specified mode.
    
    Args:
        url (str): The URL of the webpage to search for PDFs.
        recursion_depth (int, optional): The maximum depth of recursion for linked webpages. Defaults to 0.
        mode (str, optional): The processing mode, either 'separate' or 'merge'. Defaults to DEFAULT_MODE.
        write_dir (str, optional): The directory to write the output PDF files. Defaults to DEFAULT_WRITE_DIR.
    """
    # Find PDF links from the webpage
    pdf_links = find_pdfs_from_webpage(url, recursion_depth)
    print(pdf_links)

    # Process the PDFs based on the specified mode
    process_pdfs(pdf_links, write_dir, mode)