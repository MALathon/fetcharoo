"""
Integration tests for fetcharoo library.

These tests verify end-to-end workflows with mocked HTTP requests using the responses library.
"""

import os
import time
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
import pymupdf
import responses

from fetcharoo.fetcharoo import (
    download_pdfs_from_webpage,
    find_pdfs_from_webpage,
    process_pdfs,
    sanitize_filename,
)


class TestIntegration(unittest.TestCase):
    """Integration tests for full workflow scenarios."""

    def setUp(self):
        """Set up test fixtures - create sample PDF content."""
        # Create a small valid PDF document in memory
        pdf_doc = pymupdf.open()
        pdf_doc.new_page()
        self.mock_pdf_content = pdf_doc.write()
        pdf_doc.close()

        # Create a second PDF with different content
        pdf_doc2 = pymupdf.open()
        page = pdf_doc2.new_page()
        page.insert_text((100, 100), "Test PDF 2")
        self.mock_pdf_content_2 = pdf_doc2.write()
        pdf_doc2.close()

        # Create corrupted PDF content
        self.corrupted_pdf_content = b"Not a valid PDF content"

    def tearDown(self):
        """Clean up after tests."""
        pass

    # ============================================================================
    # Full Workflow Tests
    # ============================================================================

    @responses.activate
    def test_download_and_merge_workflow(self):
        """Test 1: Find PDFs on page, download them, merge into single file."""
        # Define HTML content with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/doc1.pdf">Document 1</a>
                <a href="https://example.com/doc2.pdf">Document 2</a>
            </body>
        </html>
        """

        # Mock HTTP responses
        responses.add(
            responses.GET,
            "https://example.com",
            body=html_content,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/doc1.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/doc2.pdf",
            body=self.mock_pdf_content_2,
            status=200,
            content_type="application/pdf",
        )

        # Test the full workflow with merge mode
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url="https://example.com",
                recursion_depth=0,
                mode="merge",
                write_dir=temp_dir,
            )

            # Verify success
            self.assertTrue(result)

            # Verify merged PDF file exists
            merged_pdf_path = os.path.join(temp_dir, "merged.pdf")
            self.assertTrue(os.path.exists(merged_pdf_path))

            # Verify the merged PDF has pages from both PDFs
            merged_doc = pymupdf.open(merged_pdf_path)
            self.assertEqual(merged_doc.page_count, 2)
            merged_doc.close()

    @responses.activate
    def test_download_and_separate_workflow(self):
        """Test 2: Find PDFs, save as separate files."""
        # Define HTML content with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/report.pdf">Report</a>
                <a href="https://example.com/manual.pdf">Manual</a>
            </body>
        </html>
        """

        # Mock HTTP responses
        responses.add(
            responses.GET,
            "https://example.com",
            body=html_content,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/report.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/manual.pdf",
            body=self.mock_pdf_content_2,
            status=200,
            content_type="application/pdf",
        )

        # Test the full workflow with separate mode
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url="https://example.com",
                recursion_depth=0,
                mode="separate",
                write_dir=temp_dir,
            )

            # Verify success
            self.assertTrue(result)

            # Verify both PDF files exist
            report_path = os.path.join(temp_dir, "report.pdf")
            manual_path = os.path.join(temp_dir, "manual.pdf")
            self.assertTrue(os.path.exists(report_path))
            self.assertTrue(os.path.exists(manual_path))

            # Verify each PDF has correct content
            report_doc = pymupdf.open(report_path)
            manual_doc = pymupdf.open(manual_path)
            self.assertEqual(report_doc.page_count, 1)
            self.assertEqual(manual_doc.page_count, 1)
            report_doc.close()
            manual_doc.close()

    @responses.activate
    def test_recursive_crawl_finds_nested_pdfs(self):
        """Test 3: Page links to subpage which has PDFs."""
        # Main page HTML with link to subpage
        main_html = """
        <html>
            <body>
                <a href="https://example.com/main.pdf">Main PDF</a>
                <a href="https://example.com/docs/">Documentation</a>
            </body>
        </html>
        """

        # Subpage HTML with nested PDF
        subpage_html = """
        <html>
            <body>
                <a href="https://example.com/docs/nested.pdf">Nested PDF</a>
            </body>
        </html>
        """

        # Mock HTTP responses
        responses.add(
            responses.GET,
            "https://example.com",
            body=main_html,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/docs/",
            body=subpage_html,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/main.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/docs/nested.pdf",
            body=self.mock_pdf_content_2,
            status=200,
            content_type="application/pdf",
        )

        # Test recursive crawl with depth 1
        pdf_links = find_pdfs_from_webpage(
            url="https://example.com", recursion_depth=1
        )

        # Verify both PDFs are found
        self.assertEqual(len(pdf_links), 2)
        self.assertIn("https://example.com/main.pdf", pdf_links)
        self.assertIn("https://example.com/docs/nested.pdf", pdf_links)

    @responses.activate
    def test_recursive_crawl_respects_domain_restriction(self):
        """Test 4: External links are NOT followed."""
        # HTML with internal and external links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/internal.pdf">Internal PDF</a>
                <a href="https://external.com/external.html">External Site</a>
            </body>
        </html>
        """

        # External page (should not be accessed)
        external_html = """
        <html>
            <body>
                <a href="https://external.com/external.pdf">External PDF</a>
            </body>
        </html>
        """

        # Mock HTTP responses
        responses.add(
            responses.GET,
            "https://example.com",
            body=html_content,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/internal.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        # Note: We don't add mock for external.com - it should never be called

        # Test recursive crawl with depth 1
        pdf_links = find_pdfs_from_webpage(
            url="https://example.com", recursion_depth=1
        )

        # Verify only internal PDF is found
        self.assertEqual(len(pdf_links), 1)
        self.assertIn("https://example.com/internal.pdf", pdf_links)
        # Verify external domain was not accessed
        for call in responses.calls:
            self.assertNotIn("external.com", call.request.url)

    @responses.activate
    def test_duplicate_pdf_links_handled(self):
        """Test 5: Same PDF linked twice only downloaded once."""
        # HTML with duplicate PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/doc.pdf">Document Link 1</a>
                <a href="https://example.com/doc.pdf">Document Link 2</a>
                <a href="https://example.com/other.pdf">Other Document</a>
            </body>
        </html>
        """

        # Mock HTTP responses
        responses.add(
            responses.GET,
            "https://example.com",
            body=html_content,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/doc.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/other.pdf",
            body=self.mock_pdf_content_2,
            status=200,
            content_type="application/pdf",
        )

        # Test finding PDFs
        pdf_links = find_pdfs_from_webpage(url="https://example.com", recursion_depth=0)

        # Verify doc.pdf appears only once in results
        self.assertEqual(len(pdf_links), 2)
        self.assertEqual(pdf_links.count("https://example.com/doc.pdf"), 1)
        self.assertEqual(pdf_links.count("https://example.com/other.pdf"), 1)

    @responses.activate
    def test_filename_collision_creates_numbered_files(self):
        """Test 6: Two PDFs named 'doc.pdf' become doc.pdf and doc_1.pdf."""
        # Two different URLs both named doc.pdf
        pdf_links = [
            "https://example.com/folder1/doc.pdf",
            "https://example.com/folder2/doc.pdf",
        ]

        # Mock PDF downloads
        responses.add(
            responses.GET,
            "https://example.com/folder1/doc.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/folder2/doc.pdf",
            body=self.mock_pdf_content_2,
            status=200,
            content_type="application/pdf",
        )

        # Test processing PDFs in separate mode
        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, write_dir=temp_dir, mode="separate")

            # Verify success
            self.assertTrue(result)

            # Verify both files exist with collision handling
            doc_path = os.path.join(temp_dir, "doc.pdf")
            doc_1_path = os.path.join(temp_dir, "doc_1.pdf")
            self.assertTrue(os.path.exists(doc_path))
            self.assertTrue(os.path.exists(doc_1_path))

            # Verify they contain different content
            doc1 = pymupdf.open(doc_path)
            doc2 = pymupdf.open(doc_1_path)
            self.assertEqual(doc1.page_count, 1)
            self.assertEqual(doc2.page_count, 1)
            doc1.close()
            doc2.close()

    # ============================================================================
    # Rate Limiting Test
    # ============================================================================

    @responses.activate
    @patch("time.sleep")
    def test_rate_limiting_delays_between_requests(self, mock_sleep):
        """Test 7: Verify time.sleep is called between recursive requests."""
        # Main page with two subpages
        main_html = """
        <html>
            <body>
                <a href="https://example.com/page1.html">Page 1</a>
                <a href="https://example.com/page2.html">Page 2</a>
            </body>
        </html>
        """

        subpage1_html = """
        <html>
            <body>
                <a href="https://example.com/doc1.pdf">Doc 1</a>
            </body>
        </html>
        """

        subpage2_html = """
        <html>
            <body>
                <a href="https://example.com/doc2.pdf">Doc 2</a>
            </body>
        </html>
        """

        # Mock HTTP responses
        responses.add(
            responses.GET,
            "https://example.com",
            body=main_html,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/page1.html",
            body=subpage1_html,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/page2.html",
            body=subpage2_html,
            status=200,
            content_type="text/html",
        )

        # Test recursive crawl with custom delay
        custom_delay = 1.5
        pdf_links = find_pdfs_from_webpage(
            url="https://example.com",
            recursion_depth=1,
            request_delay=custom_delay,
        )

        # Verify sleep was called for rate limiting
        # Should be called between recursive page requests (2 subpages = 2 sleeps)
        self.assertGreaterEqual(mock_sleep.call_count, 2)
        # Verify sleep was called with correct delay
        for call in mock_sleep.call_args_list:
            self.assertEqual(call[0][0], custom_delay)

    # ============================================================================
    # Mixed Content Tests
    # ============================================================================

    @responses.activate
    def test_mixed_valid_invalid_pdfs(self):
        """Test 8: Some PDFs valid, some corrupt, valid ones still saved."""
        pdf_links = [
            "https://example.com/valid1.pdf",
            "https://example.com/corrupted.pdf",
            "https://example.com/valid2.pdf",
        ]

        # Mock PDF downloads - mix of valid and corrupted
        responses.add(
            responses.GET,
            "https://example.com/valid1.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/corrupted.pdf",
            body=self.corrupted_pdf_content,
            status=200,
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/valid2.pdf",
            body=self.mock_pdf_content_2,
            status=200,
            content_type="application/pdf",
        )

        # Test processing mixed content
        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, write_dir=temp_dir, mode="separate")

            # Should succeed because at least one PDF is valid
            self.assertTrue(result)

            # Verify only valid PDFs were saved
            valid1_path = os.path.join(temp_dir, "valid1.pdf")
            valid2_path = os.path.join(temp_dir, "valid2.pdf")
            corrupted_path = os.path.join(temp_dir, "corrupted.pdf")

            self.assertTrue(os.path.exists(valid1_path))
            self.assertTrue(os.path.exists(valid2_path))
            self.assertFalse(os.path.exists(corrupted_path))

    @responses.activate
    def test_page_with_no_pdfs(self):
        """Test 9: Returns empty list, no errors."""
        # HTML with no PDF links
        html_content = """
        <html>
            <body>
                <h1>Welcome</h1>
                <a href="https://example.com/about.html">About</a>
                <a href="https://example.com/contact.html">Contact</a>
            </body>
        </html>
        """

        # Mock HTTP response
        responses.add(
            responses.GET,
            "https://example.com",
            body=html_content,
            status=200,
            content_type="text/html",
        )

        # Test finding PDFs
        pdf_links = find_pdfs_from_webpage(url="https://example.com", recursion_depth=0)

        # Verify empty list is returned
        self.assertEqual(pdf_links, [])

        # Test processing empty list
        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, write_dir=temp_dir, mode="separate")

            # Should return False but no errors
            self.assertFalse(result)

    # ============================================================================
    # Security Integration Tests
    # ============================================================================

    @responses.activate
    def test_ssrf_protection_blocks_external_domains(self):
        """Test 10: Recursive crawl stays on original domain."""
        # HTML with mixed internal and external links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/internal.html">Internal</a>
                <a href="https://evil.com/malicious.html">External</a>
                <a href="http://attacker.com/payload.html">Attacker</a>
            </body>
        </html>
        """

        internal_html = """
        <html>
            <body>
                <a href="https://example.com/safe.pdf">Safe PDF</a>
            </body>
        </html>
        """

        # Mock HTTP responses - only for allowed domain
        responses.add(
            responses.GET,
            "https://example.com",
            body=html_content,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/internal.html",
            body=internal_html,
            status=200,
            content_type="text/html",
        )
        responses.add(
            responses.GET,
            "https://example.com/safe.pdf",
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )

        # Test recursive crawl - should only access example.com
        pdf_links = find_pdfs_from_webpage(
            url="https://example.com", recursion_depth=1
        )

        # Verify only internal PDF was found
        self.assertEqual(len(pdf_links), 1)
        self.assertEqual(pdf_links[0], "https://example.com/safe.pdf")

        # Verify no requests were made to external domains
        for call in responses.calls:
            parsed_url = call.request.url
            self.assertIn("example.com", parsed_url)
            self.assertNotIn("evil.com", parsed_url)
            self.assertNotIn("attacker.com", parsed_url)

    @responses.activate
    def test_path_traversal_in_pdf_filename_sanitized(self):
        """Test 11: PDF named '../../../etc/passwd.pdf' saved safely."""
        # Malicious PDF filename with path traversal
        malicious_url = "https://example.com/../../../etc/passwd.pdf"

        # Mock PDF download
        responses.add(
            responses.GET,
            malicious_url,
            body=self.mock_pdf_content,
            status=200,
            content_type="application/pdf",
        )

        # Test processing malicious filename
        with TemporaryDirectory() as temp_dir:
            pdf_links = [malicious_url]
            result = process_pdfs(pdf_links, write_dir=temp_dir, mode="separate")

            # Verify success
            self.assertTrue(result)

            # Verify file was saved with sanitized name in temp_dir
            # Should be saved as "passwd.pdf" in temp_dir, not in /etc/
            expected_path = os.path.join(temp_dir, "passwd.pdf")
            self.assertTrue(os.path.exists(expected_path))

            # Verify file is inside temp_dir (not escaped)
            self.assertTrue(os.path.commonpath([temp_dir, expected_path]) == temp_dir)

            # Verify no files were created outside temp_dir
            etc_path = "/etc/passwd.pdf"
            self.assertFalse(os.path.exists(etc_path))

    def test_sanitize_filename_security(self):
        """Additional test: Verify sanitize_filename handles various attacks."""
        # Test path traversal
        self.assertEqual(sanitize_filename("../../../etc/passwd.pdf"), "passwd.pdf")
        # Windows-style paths - backslashes are removed
        result = sanitize_filename("..\\..\\..\\windows\\system32.pdf")
        # Verify dangerous characters removed and safe filename
        self.assertNotIn("\\", result)
        self.assertNotIn("..", result)

        # Test absolute paths
        self.assertEqual(sanitize_filename("/etc/passwd.pdf"), "passwd.pdf")
        # Windows absolute path - backslashes removed
        result2 = sanitize_filename("C:\\Windows\\System32.pdf")
        self.assertNotIn("\\", result2)
        self.assertNotIn(":", result2)

        # Test null bytes
        self.assertEqual(sanitize_filename("malicious\x00.pdf"), "malicious.pdf")

        # Test empty or hidden filenames
        self.assertEqual(sanitize_filename(""), "downloaded.pdf")
        self.assertEqual(sanitize_filename("..."), "downloaded.pdf")
        self.assertEqual(sanitize_filename(".hidden.pdf"), "hidden.pdf")

        # Test dangerous characters
        self.assertEqual(sanitize_filename('doc<>:"|?*.pdf'), "doc_______.pdf")

        # Test URL encoded path traversal
        self.assertEqual(sanitize_filename("%2e%2e%2f%2e%2e%2fetc%2fpasswd.pdf"), "passwd.pdf")

    @responses.activate
    def test_multiple_filename_collisions(self):
        """Extended test: Multiple PDFs with same name create sequence."""
        # Three different URLs all named "document.pdf"
        pdf_links = [
            "https://example.com/v1/document.pdf",
            "https://example.com/v2/document.pdf",
            "https://example.com/v3/document.pdf",
        ]

        # Mock PDF downloads
        for url in pdf_links:
            responses.add(
                responses.GET,
                url,
                body=self.mock_pdf_content,
                status=200,
                content_type="application/pdf",
            )

        # Test processing PDFs
        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, write_dir=temp_dir, mode="separate")

            # Verify success
            self.assertTrue(result)

            # Verify all three files exist with proper numbering
            doc_path = os.path.join(temp_dir, "document.pdf")
            doc_1_path = os.path.join(temp_dir, "document_1.pdf")
            doc_2_path = os.path.join(temp_dir, "document_2.pdf")

            self.assertTrue(os.path.exists(doc_path))
            self.assertTrue(os.path.exists(doc_1_path))
            self.assertTrue(os.path.exists(doc_2_path))

    @responses.activate
    def test_recursive_depth_limit(self):
        """Test that recursion depth is properly respected and limited."""
        # Create a chain of pages: main -> sub1 -> sub2 -> sub3
        main_html = '<html><body><a href="https://example.com/sub1">Sub1</a></body></html>'
        sub1_html = '<html><body><a href="https://example.com/sub2">Sub2</a></body></html>'
        sub2_html = '<html><body><a href="https://example.com/sub3">Sub3</a><a href="https://example.com/doc.pdf">PDF</a></body></html>'
        sub3_html = '<html><body><a href="https://example.com/deep.pdf">Deep PDF</a></body></html>'

        # Mock responses
        responses.add(responses.GET, "https://example.com", body=main_html, status=200)
        responses.add(responses.GET, "https://example.com/sub1", body=sub1_html, status=200)
        responses.add(responses.GET, "https://example.com/sub2", body=sub2_html, status=200)
        responses.add(responses.GET, "https://example.com/sub3", body=sub3_html, status=200)
        responses.add(
            responses.GET,
            "https://example.com/doc.pdf",
            body=self.mock_pdf_content,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://example.com/deep.pdf",
            body=self.mock_pdf_content_2,
            status=200,
        )

        # Test with depth 2 - should find doc.pdf but not deep.pdf
        pdf_links = find_pdfs_from_webpage(
            url="https://example.com", recursion_depth=2
        )

        # Should find doc.pdf at depth 2
        self.assertIn("https://example.com/doc.pdf", pdf_links)

        # Test with depth 3 - should find both
        pdf_links_deep = find_pdfs_from_webpage(
            url="https://example.com", recursion_depth=3
        )

        # Should find both PDFs
        self.assertIn("https://example.com/doc.pdf", pdf_links_deep)
        self.assertIn("https://example.com/deep.pdf", pdf_links_deep)


if __name__ == "__main__":
    unittest.main()
