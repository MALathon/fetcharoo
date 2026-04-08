"""Schema for downloading IETF RFCs."""

from fetcharoo.schemas.base import SiteSchema

IETF_RFC_SCHEMA = SiteSchema(
    name="ietf_rfc",
    url_pattern=r"https?://(www\.)?rfc-editor\.org/.*|https?://datatracker\.ietf\.org/doc/.*",
    description="IETF RFC Editor — Internet standards and specifications",
    include_patterns=["rfc*.pdf"],
    exclude_patterns=["*draft*"],
    url_include_patterns=[],
    url_exclude_patterns=["*/obsoleted-by/*"],
    sort_by="numeric",
    default_output_name="rfc_collection.pdf",
    recommended_depth=1,
    request_delay=0.5,
    test_url="https://www.rfc-editor.org/rfc/rfc9110",
    expected_min_pdfs=1,
    version="1.0.0",
)
