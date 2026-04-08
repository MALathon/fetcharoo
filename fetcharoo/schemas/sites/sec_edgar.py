"""Schema for downloading SEC EDGAR filings."""

from fetcharoo.schemas.base import SiteSchema

SEC_EDGAR_SCHEMA = SiteSchema(
    name="sec_edgar",
    url_pattern=r"https?://(www\.)?sec\.gov/cgi-bin/browse-edgar.*|https?://efts\.sec\.gov/.*|https?://(www\.)?sec\.gov/Archives/.*",
    description="SEC EDGAR — Company filings (10-K, 10-Q, 8-K, etc.)",
    include_patterns=[],
    exclude_patterns=["*R9999*", "*ex21*"],
    url_include_patterns=["*Archives/edgar/data/*"],
    url_exclude_patterns=["*/index.*"],
    sort_by="alpha",
    default_output_name="sec_filing.pdf",
    recommended_depth=2,
    request_delay=0.5,  # SEC asks for <= 10 requests/second
    test_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=apple",
    expected_min_pdfs=1,
    version="1.0.0",
)
