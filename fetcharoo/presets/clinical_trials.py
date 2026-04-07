"""
Preset configuration for monitoring ClinicalTrials.gov MCP servers.

Works with common clinical trials MCP servers including:
- cyanheads/clinicaltrialsgov-mcp-server
- JackKuo666/ClinicalTrials-MCP-Server
- Augmented-Nature/ClinicalTrials-MCP-Server
- MALathon/trial-guide

All of these wrap the ClinicalTrials.gov API v2, so the data model is consistent.

Usage:
    from fetcharoo.presets.clinical_trials import CLINICAL_TRIALS_PRESET
    from fetcharoo.mcp_monitor import SnapshotStore, snapshot_data

    # If you already have data from your MCP server:
    store = SnapshotStore()
    diff = snapshot_data(
        store=store,
        source_key="diabetes-recruiting",
        records=studies,  # list of study dicts from your MCP server
        record_id_field=CLINICAL_TRIALS_PRESET["record_id_field"],
    )

    # Or use the async MCP client to call the server directly:
    from fetcharoo.mcp_monitor import snapshot_mcp_tool
    diff = await snapshot_mcp_tool(
        store=store,
        server_command=CLINICAL_TRIALS_PRESET["server_command"],
        tool_name="search_studies",
        tool_params={"query.cond": "diabetes", "filter.overallStatus": "RECRUITING"},
        record_id_field=CLINICAL_TRIALS_PRESET["record_id_field"],
        results_field=CLINICAL_TRIALS_PRESET["results_field"],
    )
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --- ClinicalTrials.gov API v2 field paths ---
# These are the standard nested paths in the API v2 response.
# All MCP servers wrapping this API use the same structure.

# The unique identifier for each study
NCTID_FIELD = "protocolSection.identificationModule.nctId"

# Common fields for display/summary
TITLE_FIELD = "protocolSection.identificationModule.officialTitle"
BRIEF_TITLE_FIELD = "protocolSection.identificationModule.briefTitle"
STATUS_FIELD = "protocolSection.statusModule.overallStatus"
PHASE_FIELD = "protocolSection.designModule.phases"
CONDITIONS_FIELD = "protocolSection.conditionsModule.conditions"
INTERVENTIONS_FIELD = "protocolSection.armsInterventionsModule.interventions"
SPONSOR_FIELD = "protocolSection.sponsorCollaboratorsModule.leadSponsor.name"
ENROLLMENT_FIELD = "protocolSection.designModule.enrollmentInfo.count"
START_DATE_FIELD = "protocolSection.statusModule.startDateStruct.date"
LAST_UPDATE_FIELD = "protocolSection.statusModule.lastUpdatePostDateStruct.date"

# Where results are nested in common MCP server responses
# Different servers may nest results differently:
COMMON_RESULTS_FIELDS = ["studies", "results", "data", "items"]


@dataclass
class ClinicalTrialsPreset:
    """Configuration preset for clinical trials MCP monitoring."""
    record_id_field: str = NCTID_FIELD
    results_field: Optional[str] = "studies"
    server_command: Optional[List[str]] = None

    # Fields to extract for human-readable summaries
    summary_fields: Dict[str, str] = field(default_factory=lambda: {
        "nct_id": NCTID_FIELD,
        "title": BRIEF_TITLE_FIELD,
        "status": STATUS_FIELD,
        "phase": PHASE_FIELD,
        "conditions": CONDITIONS_FIELD,
        "sponsor": SPONSOR_FIELD,
        "enrollment": ENROLLMENT_FIELD,
        "start_date": START_DATE_FIELD,
        "last_update": LAST_UPDATE_FIELD,
    })

    def format_record_summary(self, record: Dict[str, Any]) -> str:
        """Format a study record into a readable one-line summary."""
        from fetcharoo.mcp_monitor import _extract_nested

        nct_id = _extract_nested(record, self.record_id_field) or "Unknown"
        title = _extract_nested(record, BRIEF_TITLE_FIELD) or "Untitled"
        status = _extract_nested(record, STATUS_FIELD) or "Unknown"
        phase = _extract_nested(record, PHASE_FIELD)
        if isinstance(phase, list):
            phase = ", ".join(str(p) for p in phase)
        phase_str = f" [{phase}]" if phase else ""

        return f"{nct_id}: {title} ({status}{phase_str})"

    def format_diff_summary(self, diff) -> str:
        """Format a SnapshotDiff into a clinical-trials-specific summary."""
        lines = [f"Clinical Trials Monitor — {diff.source_key}"]
        lines.append(f"  {diff.summary}")
        lines.append("")

        if diff.new:
            lines.append("  New trials:")
            for rec in diff.new:
                lines.append(f"    + {self.format_record_summary(rec.data)}")

        if diff.changed:
            lines.append("  Updated trials:")
            for rec in diff.changed:
                lines.append(f"    ~ {self.format_record_summary(rec.data)}")

        if diff.removed:
            lines.append("  Removed trials:")
            for rec in diff.removed:
                lines.append(f"    - {self.format_record_summary(rec.data)}")

        if not diff.has_changes:
            lines.append("  No changes since last check.")

        return "\n".join(lines)


# Default preset instance
CLINICAL_TRIALS_PRESET = ClinicalTrialsPreset()


# --- Alternative record_id_field values for different MCP server formats ---
# Some servers flatten the structure. Try these if the default doesn't work:

ALTERNATIVE_ID_FIELDS = [
    "protocolSection.identificationModule.nctId",  # Standard API v2 nested
    "nctId",                                         # Flattened by some servers
    "NCTId",                                         # Alternative casing
    "id",                                            # Generic
    "study_id",                                      # Some custom servers
    "trialId",                                       # Another variant
]
