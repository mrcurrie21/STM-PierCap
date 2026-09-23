"""Stable version and provenance metadata for calculation artifacts."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TOOL_VERSION = "0.1.0"
PIER_CAP_NOTEBOOK_VERSION = "1.0.0"
HTML_REPORT_VERSION = "1.0.0"


def _fingerprint(value):
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _git_revision(repo_root):
    if repo_root is None:
        return "unavailable", None
    root = Path(repo_root)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=root,
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=root,
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return "unavailable", None


def build_calculation_metadata(
    *, inputs, results, project_revision="0", repo_root=None, generated_at=None,
):
    """Return auditable version, source, and calculation fingerprint metadata."""
    commit, dirty = _git_revision(repo_root)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "project_revision": str(project_revision),
        "tool_version": TOOL_VERSION,
        "notebook_template_version": PIER_CAP_NOTEBOOK_VERSION,
        "html_report_version": HTML_REPORT_VERSION,
        "input_fingerprint": _fingerprint(inputs),
        "result_fingerprint": _fingerprint(results),
        "source_commit": commit,
        "source_worktree_dirty": dirty,
        "generated_at_utc": timestamp,
    }
