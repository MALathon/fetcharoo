"""
Comprehensive unit tests for security functions in fetcharoo.

This module tests the security-critical functions that prevent:
- Unauthorized domain access (is_safe_domain)
- Path traversal attacks (sanitize_filename)
"""

import pytest
from fetcharoo.fetcharoo import is_safe_domain, sanitize_filename


class TestIsSafeDomain:
    """Test suite for is_safe_domain function that validates URL domains."""

    def test_returns_true_when_allowed_domains_is_none(self):
        """
        When allowed_domains is None, all domains should be allowed.
        This is the default behavior allowing unrestricted domain access.
        """
        assert is_safe_domain('https://example.com', None) is True
        assert is_safe_domain('https://evil.com', None) is True
        assert is_safe_domain('http://any-domain.org', None) is True

    def test_exact_domain_match(self):
        """
        Test exact domain matching where URL domain must match allowed domain exactly.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://example.com', allowed) is True
        assert is_safe_domain('http://example.com', allowed) is True
        assert is_safe_domain('https://example.com/path/to/page', allowed) is True

    def test_subdomain_match(self):
        """
        Test that subdomains are correctly matched to their parent domain.
        If example.com is allowed, then sub.example.com should also be allowed.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://sub.example.com', allowed) is True
        assert is_safe_domain('https://api.example.com', allowed) is True
        assert is_safe_domain('https://deep.nested.sub.example.com', allowed) is True

    def test_subdomain_does_not_match_partial_domain(self):
        """
        Test that partial domain matches are rejected.
        If example.com is allowed, notexample.com should NOT match.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://notexample.com', allowed) is False
        assert is_safe_domain('https://fakeexample.com', allowed) is False

    def test_port_stripping(self):
        """
        Test that port numbers are correctly stripped from domain comparison.
        example.com:8080 should match example.com in the allowed list.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://example.com:8080', allowed) is True
        assert is_safe_domain('http://example.com:3000', allowed) is True
        assert is_safe_domain('https://sub.example.com:443', allowed) is True

    def test_case_insensitivity(self):
        """
        Test that domain matching is case-insensitive.
        EXAMPLE.COM should match example.com in the allowed list.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://EXAMPLE.COM', allowed) is True
        assert is_safe_domain('https://Example.Com', allowed) is True
        assert is_safe_domain('https://SUB.EXAMPLE.COM', allowed) is True

    def test_case_insensitivity_in_allowed_domains(self):
        """
        Test that allowed domains list is also case-insensitive.
        If EXAMPLE.COM is in allowed list, example.com should match.
        """
        allowed = {'EXAMPLE.COM'}
        assert is_safe_domain('https://example.com', allowed) is True
        assert is_safe_domain('https://sub.example.com', allowed) is True

    def test_returns_false_for_non_matching_domain(self):
        """
        Test that domains not in the allowed list are rejected.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://evil.com', allowed) is False
        assert is_safe_domain('https://attacker.org', allowed) is False
        assert is_safe_domain('https://different-domain.com', allowed) is False

    def test_invalid_url_handling(self):
        """
        Test that invalid URLs are handled gracefully and return False.
        """
        allowed = {'example.com'}
        assert is_safe_domain('not-a-url', allowed) is False
        assert is_safe_domain('', allowed) is False
        assert is_safe_domain('htp://broken', allowed) is False

    def test_multiple_allowed_domains(self):
        """
        Test that multiple domains can be allowed simultaneously.
        """
        allowed = {'example.com', 'trusted.org', 'safe.net'}
        assert is_safe_domain('https://example.com', allowed) is True
        assert is_safe_domain('https://trusted.org', allowed) is True
        assert is_safe_domain('https://safe.net', allowed) is True
        assert is_safe_domain('https://sub.trusted.org', allowed) is True
        assert is_safe_domain('https://evil.com', allowed) is False

    def test_url_with_path_and_query(self):
        """
        Test that URLs with paths and query parameters are correctly validated.
        The domain should be extracted properly regardless of URL complexity.
        """
        allowed = {'example.com'}
        assert is_safe_domain('https://example.com/path/to/file.pdf?query=1', allowed) is True
        assert is_safe_domain('https://sub.example.com/page?a=1&b=2#hash', allowed) is True

    def test_url_without_scheme(self):
        """
        Test handling of URLs without scheme (protocol).
        These should still be parsed correctly if possible.
        """
        allowed = {'example.com'}
        # URLs without scheme may not have netloc, so they should return False
        assert is_safe_domain('example.com/path', allowed) is False

    def test_empty_allowed_domains_set(self):
        """
        Test that an empty allowed_domains set rejects all URLs.
        """
        allowed = set()
        assert is_safe_domain('https://example.com', allowed) is False
        assert is_safe_domain('https://any-domain.com', allowed) is False


class TestSanitizeFilename:
    """Test suite for sanitize_filename function that prevents path traversal attacks."""

    def test_basic_path_traversal_unix(self):
        """
        Test that Unix-style path traversal attempts are blocked.
        "../" sequences should be removed to prevent directory escape.
        """
        assert sanitize_filename('../../../etc/passwd') == 'passwd.pdf'
        assert sanitize_filename('../../secret.pdf') == 'secret.pdf'
        assert sanitize_filename('../file.pdf') == 'file.pdf'

    def test_basic_path_traversal_windows(self):
        """
        Test that Windows-style path traversal attempts are blocked.
        "..\\" sequences should be removed to prevent directory escape.
        Note: os.path.basename() is platform-specific, so on Linux it won't
        recognize backslashes as path separators, but they are still removed.
        """
        # After os.path.basename (no-op on Linux) and backslash removal
        assert sanitize_filename('..\\..\\windows\\system32') == 'windowssystem32.pdf'
        assert sanitize_filename('..\\..\\secret.pdf') == 'secret.pdf'
        assert sanitize_filename('..\\file.pdf') == 'file.pdf'

    def test_mixed_path_separators(self):
        """
        Test that mixed Unix and Windows path separators are handled.
        Forward slashes are processed by os.path.basename, backslashes are removed.
        """
        # os.path.basename gets 'path\\file.pdf', then backslashes removed
        assert sanitize_filename('../..\\mixed/path\\file.pdf') == 'pathfile.pdf'
        assert sanitize_filename('..\\../tricky.pdf') == 'tricky.pdf'

    def test_url_encoded_traversal(self):
        """
        Test that URL-encoded path traversal attempts are decoded and blocked.
        %2e%2e%2f is the URL encoding of "../"
        After URL decoding, os.path.basename extracts the final component.
        """
        # Decodes to '../etc/passwd', basename gets 'passwd'
        assert sanitize_filename('%2e%2e%2fetc%2fpasswd') == 'passwd.pdf'
        # Decodes to '../../secret.pdf', basename gets 'secret.pdf'
        assert sanitize_filename('%2e%2e%2f%2e%2e%2fsecret.pdf') == 'secret.pdf'
        # Decodes to '..\..\windows', backslashes removed on Linux
        assert sanitize_filename('%2e%2e%5c%2e%2e%5cwindows') == 'windows.pdf'

    def test_null_byte_injection(self):
        """
        Test that null byte injection attempts are blocked.
        Null bytes can truncate filenames in some systems.
        """
        assert sanitize_filename('file\x00.pdf') == 'file.pdf'
        assert sanitize_filename('malicious\x00.exe.pdf') == 'malicious.exe.pdf'
        assert sanitize_filename('\x00hidden.pdf') == 'hidden.pdf'

    def test_empty_filename(self):
        """
        Test that empty filenames return the default 'downloaded.pdf'.
        """
        assert sanitize_filename('') == 'downloaded.pdf'

    def test_only_dots_filename(self):
        """
        Test that filenames consisting only of dots return the default.
        Leading dots are stripped, leaving an empty string.
        """
        assert sanitize_filename('...') == 'downloaded.pdf'
        assert sanitize_filename('.') == 'downloaded.pdf'
        assert sanitize_filename('..') == 'downloaded.pdf'

    def test_only_extension(self):
        """
        Test that a filename that is only '.pdf' becomes 'pdf.pdf'.
        The leading dot is stripped, leaving 'pdf', then .pdf is ensured.
        """
        assert sanitize_filename('.pdf') == 'pdf.pdf'

    def test_very_long_filename(self):
        """
        Test that very long filenames are truncated to 200 characters max.
        The .pdf extension should still be preserved.
        """
        long_name = 'a' * 250 + '.pdf'
        result = sanitize_filename(long_name)
        assert len(result) == 200
        assert result.endswith('.pdf')
        # Check that the truncation preserved as much of the name as possible
        assert result.startswith('a' * 196)  # 200 - 4 (.pdf)

    def test_special_characters_windows(self):
        """
        Test that Windows-forbidden characters are replaced with underscores.
        Characters: < > : " | ? *
        """
        assert sanitize_filename('file<name>.pdf') == 'file_name_.pdf'
        assert sanitize_filename('file>name.pdf') == 'file_name.pdf'
        assert sanitize_filename('file:name.pdf') == 'file_name.pdf'
        assert sanitize_filename('file"name.pdf') == 'file_name.pdf'
        assert sanitize_filename('file|name.pdf') == 'file_name.pdf'
        assert sanitize_filename('file?name.pdf') == 'file_name.pdf'
        assert sanitize_filename('file*name.pdf') == 'file_name.pdf'

    def test_all_special_characters_together(self):
        """
        Test multiple special characters in one filename.
        There are 7 special characters: < > : " | ? *
        """
        assert sanitize_filename('bad<>:"|?*chars.pdf') == 'bad_______chars.pdf'

    def test_leading_dots_removed(self):
        """
        Test that leading dots are removed (prevents hidden files on Unix).
        """
        assert sanitize_filename('.hidden.pdf') == 'hidden.pdf'
        assert sanitize_filename('..secret.pdf') == 'secret.pdf'
        assert sanitize_filename('...file.pdf') == 'file.pdf'

    def test_leading_dots_but_keep_extension(self):
        """
        Test that dots in the middle of the filename are preserved.
        """
        assert sanitize_filename('.my.file.name.pdf') == 'my.file.name.pdf'

    def test_ensures_pdf_extension(self):
        """
        Test that files without .pdf extension get it added.
        """
        assert sanitize_filename('document') == 'document.pdf'
        assert sanitize_filename('file.txt') == 'file.txt.pdf'
        assert sanitize_filename('image.jpg') == 'image.jpg.pdf'

    def test_preserves_existing_pdf_extension(self):
        """
        Test that existing .pdf extension is preserved (not duplicated).
        """
        assert sanitize_filename('document.pdf') == 'document.pdf'
        assert sanitize_filename('file.PDF') == 'file.PDF'  # Case preserved in extension

    def test_absolute_path_unix(self):
        """
        Test that absolute Unix paths are converted to just the filename.
        """
        assert sanitize_filename('/etc/passwd') == 'passwd.pdf'
        assert sanitize_filename('/home/user/document.pdf') == 'document.pdf'
        assert sanitize_filename('/var/log/file.pdf') == 'file.pdf'

    def test_absolute_path_windows(self):
        """
        Test that absolute Windows paths are handled.
        On Linux, os.path.basename doesn't recognize backslashes, so they're removed.
        The colon in drive letter (C:) is replaced with underscore.
        """
        # 'C:\\Windows\\system32\\file.pdf' -> basename keeps all, backslashes removed, : becomes _
        assert sanitize_filename('C:\\Windows\\system32\\file.pdf') == 'C_Windowssystem32file.pdf'
        # Similar for D: drive
        assert sanitize_filename('D:\\Users\\docs\\secret.pdf') == 'D_Usersdocssecret.pdf'

    def test_path_with_multiple_components(self):
        """
        Test that only the base filename is kept from complex paths.
        Forward slashes work on all platforms, backslashes only on Windows.
        """
        assert sanitize_filename('path/to/deep/nested/file.pdf') == 'file.pdf'
        # On Linux, backslashes are not path separators, so they get removed
        assert sanitize_filename('path\\to\\deep\\nested\\file.pdf') == 'pathtodeepnestedfile.pdf'

    def test_normal_filename(self):
        """
        Test that normal, safe filenames pass through with .pdf extension ensured.
        """
        assert sanitize_filename('document.pdf') == 'document.pdf'
        assert sanitize_filename('my-file_v2.pdf') == 'my-file_v2.pdf'
        assert sanitize_filename('report_2024.pdf') == 'report_2024.pdf'

    def test_unicode_filename(self):
        """
        Test that Unicode characters in filenames are preserved.
        """
        assert sanitize_filename('文档.pdf') == '文档.pdf'
        assert sanitize_filename('документ.pdf') == 'документ.pdf'
        assert sanitize_filename('café-résumé.pdf') == 'café-résumé.pdf'

    def test_spaces_in_filename(self):
        """
        Test that spaces in filenames are preserved.
        """
        assert sanitize_filename('my document.pdf') == 'my document.pdf'
        assert sanitize_filename('file with spaces.pdf') == 'file with spaces.pdf'

    def test_url_encoded_spaces(self):
        """
        Test that URL-encoded spaces (%20) are decoded.
        """
        assert sanitize_filename('my%20document.pdf') == 'my document.pdf'
        assert sanitize_filename('file%20with%20spaces.pdf') == 'file with spaces.pdf'

    def test_complex_attack_combination(self):
        """
        Test a complex attack combining multiple techniques.
        After URL decode and os.path.basename, gets final component.
        """
        malicious = '../../../%2e%2e%2f..\\..\\etc/passwd\x00.pdf'
        result = sanitize_filename(malicious)
        # After decode: '../../../../../..\\..\\etc/passwd\x00.pdf'
        # os.path.basename gets: 'passwd\x00.pdf'
        # null byte removed, result is 'passwd.pdf'
        assert result == 'passwd.pdf'
        assert '..' not in result
        assert '/' not in result
        assert '\\' not in result
        assert '\x00' not in result

    def test_filename_with_only_path_separators(self):
        """
        Test that filenames consisting only of path separators become default.
        """
        assert sanitize_filename('///') == 'downloaded.pdf'
        assert sanitize_filename('\\\\\\') == 'downloaded.pdf'
        assert sanitize_filename('/\\/\\') == 'downloaded.pdf'

    def test_truncation_preserves_extension(self):
        """
        Test that when truncating, the .pdf extension is always preserved.
        """
        # Create a filename that's exactly at the limit
        base = 'a' * 196  # 200 - 4 for '.pdf'
        result = sanitize_filename(base + '.pdf')
        assert len(result) == 200
        assert result.endswith('.pdf')
        assert result == base + '.pdf'

    def test_truncation_of_filename_without_extension(self):
        """
        Test truncation when .pdf needs to be added to a long filename.
        """
        long_name = 'b' * 250
        result = sanitize_filename(long_name)
        assert len(result) == 200
        assert result.endswith('.pdf')
        # When .pdf is added, it should truncate the base name
        expected = 'b' * 196 + '.pdf'
        assert result == expected

    def test_double_extension_handling(self):
        """
        Test filenames with double extensions like .tar.gz
        """
        assert sanitize_filename('archive.tar.gz') == 'archive.tar.gz.pdf'
        assert sanitize_filename('file.txt.bak') == 'file.txt.bak.pdf'

    def test_case_sensitivity_of_pdf_extension(self):
        """
        Test that .pdf extension check is case-insensitive.
        """
        assert sanitize_filename('file.PDF') == 'file.PDF'
        assert sanitize_filename('file.Pdf') == 'file.Pdf'
        assert sanitize_filename('file.pDf') == 'file.pDf'

    def test_multiple_dots_in_filename(self):
        """
        Test filenames with multiple dots are handled correctly.
        """
        assert sanitize_filename('my.file.name.v2.pdf') == 'my.file.name.v2.pdf'
        assert sanitize_filename('.....lots.of.dots.pdf') == 'lots.of.dots.pdf'
