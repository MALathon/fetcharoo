"""Schema for downloading W3C specifications."""

from fetcharoo.schemas.base import SiteSchema

W3C_SCHEMA = SiteSchema(
    name="w3c",
    url_pattern=r"https?://(www\.)?w3\.org/(TR|standards)/.*",
    description="W3C — Web standards and technical reports",
    include_patterns=[],
    exclude_patterns=["*diff*", "*review*"],
    url_include_patterns=["*w3.org/TR/*"],
    url_exclude_patterns=["*/WD-*"],  # Exclude working drafts by default
    sort_by="alpha",
    default_output_name="w3c_specs.pdf",
    recommended_depth=1,
    request_delay=0.5,
    version="1.0.0",
)
