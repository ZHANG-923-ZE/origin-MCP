"""Shared utility functions used across all MCP OriginPro tools.

These helpers handle input validation, path safety, colour parsing, data
size checks, and standardized JSON response formatting.  They are
tool-agnostic and never import MCP-specific modules.
"""

from __future__ import annotations

import os
import re
from typing import Any, Sequence

from mcp_origin.core.constants import COLOR_NAMES
from mcp_origin.core.errors import ValidationError

# Maximum number of data rows allowed by default (prevents OOM / COM timeouts).
DEFAULT_MAX_ROWS = 10_000

# Regex for a valid hex colour: #rgb or #rrggbb (case-insensitive).
_HEX_COLOR_RE = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


# ============================================================================
# Colour parsing
# ============================================================================

def parse_color(color: str) -> str:
    """Accept a named colour or hex string; return a normalised hex string.

    Recognised named colours come from :data:`mcp_origin.core.constants.COLOR_NAMES`.
    Hex values are validated and normalised to lowercase ``#rrggbb``.

    Args:
        color: A case-insensitive colour name (e.g. ``"red"``) or a hex string
               (``"#FF0000"``, ``"#f00"``, ``"#fff"``).

    Returns:
        Lowercase ``#rrggbb`` hex string (6 digits, always with ``#``).

    Raises:
        ValidationError: The colour string is not recognised or malformed.
    """
    if not color or not isinstance(color, str):
        raise ValidationError(
            "Colour must be a non-empty string.",
            details={"color": color},
            hint="Use a name like 'red' or a hex value like '#FF0000'.",
        )

    color_lower = color.strip().lower()

    # Named colour lookup.
    named = COLOR_NAMES.get(color_lower)
    if named is not None:
        return named.lower()

    # Optional leading '#' (caller may have omitted it for 3/6-digit hex).
    raw = color_lower.lstrip("#")
    if len(raw) == 3:
        # Expand #abc → #aabbcc.
        raw = "".join(c * 2 for c in raw)

    if len(raw) == 6:
        try:
            int(raw, 16)  # validate hex digits only.
        except ValueError:
            raise ValidationError(
                f"Invalid hex colour '{color}'.",
                details={"color": color},
                hint="Use #rrggbb (e.g. '#FF0000') or a named colour.",
            ) from None
        return f"#{raw}"

    raise ValidationError(
        f"Unrecognised colour '{color}'.",
        details={"color": color},
        hint="Use a name like 'red' or a hex value like '#FF0000'.",
    )


# ============================================================================
# Column index validation
# ============================================================================

def validate_column_index(wks: Any, col: int) -> None:
    """Validate that a column index is within the worksheet's range.

    Column indices are **0-based** (matching Python / originpro convention).

    Args:
        wks: An originpro worksheet object (must have a ``cols`` attribute).
        col: 0-based column index to validate.

    Raises:
        ValidationError: The column index is out of range.
    """
    if not isinstance(col, int):
        raise ValidationError(
            f"Column index must be an integer, got {type(col).__name__}.",
            details={"col": col},
            hint="Pass a 0-based integer column index.",
        )

    try:
        max_cols = len(wks.cols)  # type: ignore[arg-type]
    except Exception:
        # Could not determine the column count — defer to the tool layer.
        return

    if col < 0 or col >= max_cols:
        raise ValidationError(
            f"Column index {col} is out of range (worksheet has {max_cols} columns).",
            details={"col": col, "max_cols": max_cols},
            hint=(
                f"Use a value between 0 and {max_cols - 1} inclusive. "
                "Column indices are 0-based."
            ),
        )


# ============================================================================
# Safe path handling
# ============================================================================

def safe_path(file_path: str) -> str:
    """Normalise a file path and reject attempts to escape the workspace.

    This is a security measure that prevents path-traversal attacks when
    tools accept user-supplied file paths for export / save operations.

    Args:
        file_path: A user-supplied path (relative or absolute).

    Returns:
        Absolute, normalised path string.

    Raises:
        ValidationError: The path contains ``..`` components that would
            navigate above the current working directory.
    """
    if not file_path:
        raise ValidationError(
            "File path must not be empty.",
            details={"file_path": file_path},
            hint="Provide a valid file path.",
        )

    # Resolve to absolute before checking so that clever CWD-relative
    # traversals (e.g. "../../etc/passwd") are caught.
    abs_path = os.path.abspath(file_path)
    cwd = os.getcwd()

    # After normalisation, the resolved path must start with cwd.
    # Also reject any raw ".." component as a belt-and-suspenders check.
    if ".." in file_path.replace("\\", "/").split("/"):
        raise ValidationError(
            "Path traversal detected: path contains '..'.",
            details={"file_path": file_path},
            hint="Use a safe relative or absolute path within the workspace.",
        )

    if not abs_path.startswith(cwd + os.sep) and abs_path != cwd:
        raise ValidationError(
            "Path must stay within the current working directory.",
            details={"file_path": file_path, "resolved": abs_path},
            hint="Provide a path inside the current workspace.",
        )

    return abs_path


# ============================================================================
# Data validation
# ============================================================================

def validate_data(
    data: Sequence[Sequence[Any]] | None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> None:
    """Validate that a dataset is non-empty, well-formed, and within size limits.

    The dataset should be a list of rows, where each row is itself a sequence
    of values.  This matches the shape expected by originpro's ``from_list``
    and similar bulk-data APIs.

    Args:
        data: 2-D sequence of values (list of rows).
        max_rows: Maximum number of rows allowed (default 10 000).

    Raises:
        ValidationError: The data is None, empty, malformed, or too large.
    """
    if data is None:
        raise ValidationError(
            "Data must not be None.",
            hint="Pass a list of rows, e.g. [[1, 2], [3, 4]].",
        )

    if not isinstance(data, (list, tuple)):
        raise ValidationError(
            f"Data must be a list or tuple, got {type(data).__name__}.",
            details={"data_type": type(data).__name__},
            hint="Pass a list of rows, e.g. [[1, 2], [3, 4]].",
        )

    if len(data) == 0:
        raise ValidationError(
            "Data must not be empty.",
            hint="Provide at least one row of data.",
        )

    if len(data) > max_rows:
        raise ValidationError(
            f"Data has {len(data)} rows, maximum is {max_rows}.",
            details={"row_count": len(data), "max_rows": max_rows},
            hint="Reduce the dataset size or increase max_rows.",
        )

    # Verify that every row is itself a sequence.
    for i, row in enumerate(data):
        if not isinstance(row, (list, tuple)):
            raise ValidationError(
                f"Row {i} is not a list/tuple (got {type(row).__name__}).",
                details={"row_index": i, "row_type": type(row).__name__},
                hint="Each row must be a list of values.",
            )


# ============================================================================
# Standardised response formatting
# ============================================================================

def format_response(
    success: bool,
    data: dict[str, Any] | None = None,
    error: str = "",
    hint: str = "",
) -> dict[str, Any]:
    """Produce a standardised JSON-serialisable response dict for MCP tools.

    Every tool should return this dict so the LLM receives a consistent
    envelope.

    Args:
        success: ``True`` if the operation succeeded.
        data: Payload to include on success (optional).
        error: Error message on failure.
        hint: Actionable suggestion for the LLM / user.

    Returns:
        A dict with at least ``{"success": bool}``.
    """
    response: dict[str, Any] = {"success": success}

    if success:
        if data is not None:
            response["data"] = data
    else:
        response["error"] = error or "Unknown error"
        if hint:
            response["hint"] = hint

    return response
