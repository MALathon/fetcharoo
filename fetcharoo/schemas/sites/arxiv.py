"""Schema for downloading papers from arXiv."""

from fetcharoo.schemas.base import SiteSchema

ARXIV_SCHEMA = SiteSchema(
    name="arxiv",
    url_pattern=r"https?://arxiv\.org/(abs|pdf|html)/\d+\.\d+",
    description="arXiv preprint server — academic papers and preprints",
    include_patterns=[],
    exclude_patterns=[],
    url_include_patterns=["*arxiv.org/pdf/*"],
    url_exclude_patterns=[],
    sort_by="alpha",
    default_output_name="arxiv_papers.pdf",
    recommended_depth=0,
    request_delay=1.0,  # arXiv rate-limits aggressively
    test_url="https://arxiv.org/abs/2301.00001",
    expected_min_pdfs=1,
    version="1.0.0",
)
