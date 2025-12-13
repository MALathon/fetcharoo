#!/usr/bin/env python3
"""
Demonstration script for PDF filtering functionality.

This script demonstrates how to use the filtering features without requiring
external dependencies to be installed.

Author: Mark A. Lifson, Ph.D.
"""

import sys
import os

# Add the fetcharoo directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only the filtering module directly (bypass __init__ to avoid dependencies)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "filtering",
    os.path.join(os.path.dirname(__file__), "fetcharoo", "filtering.py")
)
filtering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(filtering)

# Extract the functions we need
FilterConfig = filtering.FilterConfig
matches_filename_pattern = filtering.matches_filename_pattern
matches_size_limits = filtering.matches_size_limits
matches_url_pattern = filtering.matches_url_pattern
apply_filters = filtering.apply_filters
should_download_pdf = filtering.should_download_pdf


def test_filename_filtering():
    """Test filename pattern matching."""
    print("Testing filename filtering...")

    # Test basic wildcard matching
    assert matches_filename_pattern('report.pdf', ['*.pdf'], [])
    assert matches_filename_pattern('report_2023.pdf', ['report*.pdf'], [])
    assert not matches_filename_pattern('draft.pdf', ['report*.pdf'], [])

    # Test exclude patterns
    assert not matches_filename_pattern('draft_report.pdf', ['*.pdf'], ['*draft*'])
    assert matches_filename_pattern('final_report.pdf', ['*.pdf'], ['*draft*'])

    print("  ✓ Filename filtering tests passed")


def test_size_filtering():
    """Test file size filtering."""
    print("Testing size filtering...")

    # Test within limits
    assert matches_size_limits(5000, min_size=1000, max_size=10000)

    # Test below minimum
    assert not matches_size_limits(500, min_size=1000, max_size=10000)

    # Test above maximum
    assert not matches_size_limits(15000, min_size=1000, max_size=10000)

    # Test with only min
    assert matches_size_limits(5000, min_size=1000, max_size=None)

    # Test with only max
    assert matches_size_limits(5000, min_size=None, max_size=10000)

    # Test with None (unknown size)
    assert matches_size_limits(None, min_size=1000, max_size=10000)

    print("  ✓ Size filtering tests passed")


def test_url_filtering():
    """Test URL pattern matching."""
    print("Testing URL filtering...")

    # Test URL pattern matching
    assert matches_url_pattern('https://example.com/reports/annual.pdf', ['*/reports/*'], [])
    assert not matches_url_pattern('https://example.com/other/file.pdf', ['*/reports/*'], [])

    # Test exclude patterns
    assert not matches_url_pattern(
        'https://example.com/drafts/report.pdf',
        ['*example.com*'],
        ['*/drafts/*']
    )

    print("  ✓ URL filtering tests passed")


def test_combined_filtering():
    """Test combined filter logic."""
    print("Testing combined filtering...")

    config = FilterConfig(
        filename_include=['report*.pdf'],
        filename_exclude=['*draft*'],
        min_size=1000,
        max_size=100000,
        url_include=['*/documents/*'],
        url_exclude=['*/temp/*']
    )

    # Should pass all filters
    assert apply_filters(
        'https://example.com/documents/report_2023.pdf',
        5000,
        config
    )

    # Should fail filename filter
    assert not apply_filters(
        'https://example.com/documents/summary.pdf',
        5000,
        config
    )

    # Should fail size filter (too small)
    assert not apply_filters(
        'https://example.com/documents/report.pdf',
        500,
        config
    )

    # Should fail URL filter (in temp)
    assert not apply_filters(
        'https://example.com/temp/report.pdf',
        5000,
        config
    )

    # Should fail exclude pattern
    assert not apply_filters(
        'https://example.com/documents/report_draft.pdf',
        5000,
        config
    )

    print("  ✓ Combined filtering tests passed")


def test_filter_config():
    """Test FilterConfig creation and usage."""
    print("Testing FilterConfig...")

    # Test with all options
    config = FilterConfig(
        filename_include=['*.pdf'],
        filename_exclude=['*draft*'],
        min_size=1000,
        max_size=10000,
        url_include=['*/reports/*'],
        url_exclude=['*/temp/*']
    )

    assert config.filename_include == ['*.pdf']
    assert config.filename_exclude == ['*draft*']
    assert config.min_size == 1000
    assert config.max_size == 10000

    # Test with defaults
    config_default = FilterConfig()
    assert config_default.filename_include == []
    assert config_default.filename_exclude == []
    assert config_default.min_size is None
    assert config_default.max_size is None

    print("  ✓ FilterConfig tests passed")


def test_should_download_pdf():
    """Test the should_download_pdf convenience function."""
    print("Testing should_download_pdf...")

    config = FilterConfig(
        filename_include=['report*.pdf'],
        min_size=1000,
        max_size=100000
    )

    # Should pass
    assert should_download_pdf(
        'https://example.com/report_2023.pdf',
        5000,
        config
    )

    # Should fail (size too small)
    assert not should_download_pdf(
        'https://example.com/report_2023.pdf',
        500,
        config
    )

    # No config should pass all
    assert should_download_pdf(
        'https://example.com/any_file.pdf',
        500,
        None
    )

    print("  ✓ should_download_pdf tests passed")


def test_real_world_scenario():
    """Test a real-world filtering scenario."""
    print("Testing real-world scenario...")

    # Scenario: Download only annual reports from a trusted source
    config = FilterConfig(
        filename_include=['*annual*report*.pdf', '*yearly*report*.pdf'],
        filename_exclude=['*draft*', '*preliminary*'],
        url_include=['https://trusted-source.org/publications/*'],
        min_size=50000,  # At least 50KB
        max_size=10_000_000  # Max 10MB
    )

    # Should pass - valid annual report
    assert apply_filters(
        'https://trusted-source.org/publications/2023/annual_report.pdf',
        2_000_000,
        config
    )

    # Should fail - draft version
    assert not apply_filters(
        'https://trusted-source.org/publications/2023/annual_report_draft.pdf',
        2_000_000,
        config
    )

    # Should fail - too small
    assert not apply_filters(
        'https://trusted-source.org/publications/2023/annual_report.pdf',
        30_000,
        config
    )

    # Should fail - wrong domain
    assert not apply_filters(
        'https://untrusted.com/publications/2023/annual_report.pdf',
        2_000_000,
        config
    )

    print("  ✓ Real-world scenario tests passed")


def main():
    """Run all demonstration tests."""
    print("=" * 60)
    print("PDF Filtering Feature Demonstration")
    print("Author: Mark A. Lifson, Ph.D.")
    print("=" * 60)
    print()

    try:
        test_filename_filtering()
        test_size_filtering()
        test_url_filtering()
        test_combined_filtering()
        test_filter_config()
        test_should_download_pdf()
        test_real_world_scenario()

        print()
        print("=" * 60)
        print("✓ All demonstration tests passed successfully!")
        print("=" * 60)
        print()
        print("The PDF filtering feature is working correctly.")
        print("You can now use FilterConfig with download_pdfs_from_webpage")
        print("and process_pdfs functions to filter PDFs by:")
        print("  - Filename patterns (include/exclude)")
        print("  - File size limits (min/max)")
        print("  - URL patterns (include/exclude)")
        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
