"""Schema for downloading Federal Register documents."""

from fetcharoo.schemas.base import SiteSchema

FEDERAL_REGISTER_SCHEMA = SiteSchema(
    name="federal_register",
    url_pattern=r"https?://(www\.)?federalregister\.gov/(documents|articles)/.*",
    description="Federal Register — U.S. government rules, proposed rules, and notices",
    include_patterns=[],
    exclude_patterns=[],
    url_include_patterns=["*federalregister.gov/*"],
    url_exclude_patterns=["*/comments/*", "*/docket*"],
    sort_by="alpha",
    default_output_name="federal_register.pdf",
    recommended_depth=1,
    request_delay=1.0,  # Be respectful to government servers
    version="1.0.0",
)
