"""
Notification handlers for fetcharoo watch mode.

Supports multiple notification channels: stdout, JSON, webhook, and command execution.
"""

import json
import logging
import os
import subprocess
from typing import List, Optional

import requests

from fetcharoo.catalog import DiffResult, DocumentRecord

logger = logging.getLogger('fetcharoo')


def format_diff_text(diff: DiffResult, url: str) -> str:
    """
    Format a DiffResult as human-readable text with git-like prefixes.

    Args:
        diff: The DiffResult to format.
        url: The source URL that was checked.

    Returns:
        Formatted text string.
    """
    lines = []
    lines.append(f"Changes detected for: {url}")
    lines.append(f"  New: {len(diff.new)}  Changed: {len(diff.changed)}  Removed: {len(diff.removed)}  Unchanged: {len(diff.unchanged)}")
    lines.append("")

    if diff.new:
        for doc in diff.new:
            lines.append(f"  + {doc.url}")
    if diff.changed:
        for doc in diff.changed:
            lines.append(f"  ~ {doc.url}")
    if diff.removed:
        for doc in diff.removed:
            lines.append(f"  - {doc.url}")

    if not diff.new and not diff.changed and not diff.removed:
        lines.append("  No changes detected.")

    return "\n".join(lines)


def format_diff_json(diff: DiffResult, url: str) -> str:
    """
    Format a DiffResult as a JSON string.

    Args:
        diff: The DiffResult to format.
        url: The source URL that was checked.

    Returns:
        JSON string.
    """
    data = {
        "source_url": url,
        "summary": {
            "new": len(diff.new),
            "changed": len(diff.changed),
            "removed": len(diff.removed),
            "unchanged": len(diff.unchanged),
        },
        "new": [doc.url for doc in diff.new],
        "changed": [doc.url for doc in diff.changed],
        "removed": [doc.url for doc in diff.removed],
    }
    return json.dumps(data, indent=2)


def notify_stdout(diff: DiffResult, url: str) -> None:
    """Print diff to stdout in human-readable format."""
    print(format_diff_text(diff, url))


def notify_json(diff: DiffResult, url: str) -> None:
    """Print diff to stdout as JSON."""
    print(format_diff_json(diff, url))


def notify_webhook(diff: DiffResult, url: str, webhook_url: str) -> bool:
    """
    POST diff as JSON to a webhook URL.

    Args:
        diff: The DiffResult to send.
        url: The source URL that was checked.
        webhook_url: The webhook URL to POST to.

    Returns:
        True if the webhook responded successfully.
    """
    payload = json.loads(format_diff_json(diff, url))
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"Webhook notification sent to {webhook_url}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Webhook notification failed: {e}")
        return False


def notify_command(diff: DiffResult, url: str, command: str) -> int:
    """
    Run a shell command with change info as environment variables.

    Environment variables set:
        FETCHAROO_URL: The source URL
        FETCHAROO_NEW_COUNT: Number of new documents
        FETCHAROO_CHANGED_COUNT: Number of changed documents
        FETCHAROO_REMOVED_COUNT: Number of removed documents
        FETCHAROO_NEW_URLS: Newline-separated list of new URLs
        FETCHAROO_CHANGED_URLS: Newline-separated list of changed URLs
        FETCHAROO_REMOVED_URLS: Newline-separated list of removed URLs

    Args:
        diff: The DiffResult.
        url: The source URL.
        command: Shell command to execute.

    Returns:
        The command's exit code.
    """
    env = os.environ.copy()
    env['FETCHAROO_URL'] = url
    env['FETCHAROO_NEW_COUNT'] = str(len(diff.new))
    env['FETCHAROO_CHANGED_COUNT'] = str(len(diff.changed))
    env['FETCHAROO_REMOVED_COUNT'] = str(len(diff.removed))
    env['FETCHAROO_NEW_URLS'] = "\n".join(doc.url for doc in diff.new)
    env['FETCHAROO_CHANGED_URLS'] = "\n".join(doc.url for doc in diff.changed)
    env['FETCHAROO_REMOVED_URLS'] = "\n".join(doc.url for doc in diff.removed)

    try:
        result = subprocess.run(
            command, shell=True, env=env, timeout=120,
            capture_output=True, text=True
        )
        if result.stdout:
            logger.info(f"Command output: {result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"Command stderr: {result.stderr.strip()}")
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {command}")
        return -1
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return -1


def has_changes(diff: DiffResult) -> bool:
    """Check if a DiffResult contains any changes."""
    return bool(diff.new or diff.changed or diff.removed)
