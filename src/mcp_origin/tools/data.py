"""MCP data tools: worksheet creation, column population, CSV import, and column metadata.

Four tools that mirror OriginPro's data-management capabilities through the
originpro COM API.  All return standardised ``{"success": bool, ...}`` dicts
and follow the same architecture pattern:
``ensure_origin() → import originpro → validate → operate → format_response``.
"""

from __future__ import annotations

import os
from typing import Any

from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.errors import (
    OriginNotRunningError,
    ToolExecutionError,
    ValidationError,
)
from mcp_origin.utils import (
    DEFAULT_MAX_ROWS,
    format_response,
    safe_path,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# User-facing axis names accepted by set_column_data.
_VALID_AXES = frozenset({"X", "Y", "Z", "X Error", "Y Error", "Label", "Disregard"})

# Map user-facing axis names → originpro API axis codes.
_AXIS_TO_CODE: dict[str, str] = {
    "X": "X",
    "Y": "Y",
    "Z": "Z",
    "X Error": "E",
    "Y Error": "E",
    "Label": "L",
    "Disregard": "N",
}

# Map originpro column-type codes → human-readable axis names (reverse lookup).
_CODE_TO_AXIS: dict[int, str] = {
    0: "Y",
    1: "Disregard",
    2: "Y Error",
    3: "X",
    4: "Label",
    5: "Z",
    6: "X Error",
}

# File extensions accepted as "CSV" by import_csv.  Origin's Data Connector
# also handles .txt (tab-delimited) and .dat.
_CSV_EXTENSIONS = frozenset({".csv", ".txt", ".dat"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_worksheet(op: Any, name: str) -> Any:
    """Resolve a worksheet by name, or return the active worksheet.

    Args:
        op: The originpro module (already imported).
        name: Worksheet name.  An empty string means "active worksheet".

    Returns:
        The originpro worksheet object.

    Raises:
        ValidationError: No worksheet matching *name* could be found.
    """
    if not name:
        wks = op.find_sheet("w")
        if wks is None:
            raise ValidationError(
                "No active worksheet.  Create or open a worksheet first.",
                hint="Use create_worksheet() to create a new sheet, or open an existing project.",
            )
        return wks

    wks = op.find_sheet("w", name)
    if wks is None:
        available = _list_worksheet_names(op)
        hint_msg = f"Worksheet '{name}' was not found."
        if available:
            hint_msg += f" Available sheets: {', '.join(available)}"
        else:
            hint_msg += " No worksheets are currently open in the project."
        raise ValidationError(
            f"Worksheet '{name}' not found.",
            details={"worksheet_name": name, "available": available},
            hint=hint_msg,
        )
    return wks


def _list_worksheet_names(op: Any) -> list[str]:
    """Best-effort listing of open worksheet names in the Origin project.

    Returns an empty list if the project is empty or if the iteration fails
    (e.g. running in a test environment without a real COM connection).
    """
    names: list[str] = []
    try:
        for idx in range(len(op.pages)):
            page = op.pages[idx]
            if hasattr(page, "type") and page.type == "w" and hasattr(page, "name"):
                names.append(page.name)
    except Exception:
        pass
    return names


def _get_column_axis(col: Any) -> str:
    """Return a human-readable axis designation for a column object.

    Falls back to ``""`` when the designation cannot be determined.
    """
    try:
        type_val = col.type
        if isinstance(type_val, int):
            return _CODE_TO_AXIS.get(type_val, str(type_val))
        return str(type_val) if type_val is not None else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# A1: create_worksheet
# ---------------------------------------------------------------------------

def create_worksheet(name: str = "") -> dict:
    """Create a new Origin worksheet and return its metadata.

    Args:
        name: Desired worksheet name.  If empty or already taken, Origin's
            auto-generated name (e.g. ``"Book1"``) is used.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``name``, ``type``, ``column_count``, ``index``.

    Example:
        >>> create_worksheet("MyData")
        {"success": true, "data": {"name": "MyData", "type": "worksheet", ...}}
    """
    try:
        ensure_origin()
        import originpro as op

        wks = op.new_sheet()

        if name:
            try:
                wks.name = name
            except Exception:
                # Name collision or invalid characters — keep Origin default.
                pass

        # wks.cols may return an int (column count) in some originpro
        # versions instead of a sequence — guard against both cases.
        try:
            col_count = len(wks.cols)
        except (TypeError, AttributeError):
            col_count = wks.cols if isinstance(wks.cols, int) else 0
        sheet_index = getattr(wks, "index", 0)

        result = {
            "name": getattr(wks, "name", ""),
            "type": "worksheet",
            "column_count": col_count,
            "index": sheet_index,
        }
        return format_response(True, data=result)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as e:
        return format_response(
            False, error=str(e), hint="An unexpected error occurred while creating the worksheet.",
        )


# ---------------------------------------------------------------------------
# A2: set_column_data
# ---------------------------------------------------------------------------

def set_column_data(
    worksheet_name: str = "",
    column: int = 0,
    data: list[float] | None = None,
    long_name: str = "",
    units: str = "",
    comments: str = "",
    axis: str = "Y",
) -> dict:
    """Populate a single column in a worksheet with numeric data.

    Args:
        worksheet_name: Target worksheet (empty = active sheet).
        column: 0‑based column index to fill.
        data: List of numeric values (max 10 000 rows).
        long_name: Column long‑name (displayed in Origin's column header row).
        units: Column units label.
        comments: Column comments.
        axis: Column designation — one of ``"X"``, ``"Y"``, ``"Z"``,
            ``"X Error"``, ``"Y Error"``, ``"Label"``, ``"Disregard"``.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``worksheet``, ``column``, ``row_count``, ``long_name``, ``units``.
    """
    try:
        # ── 1. Pre-flight checks ──────────────────────────────────────
        ensure_origin()

        if axis not in _VALID_AXES:
            raise ValidationError(
                f"Invalid axis '{axis}'.  Must be one of: {', '.join(sorted(_VALID_AXES))}.",
                details={"axis": axis, "valid_axes": sorted(_VALID_AXES)},
                hint="Use 'X', 'Y', 'Z', 'X Error', 'Y Error', 'Label', or 'Disregard'.",
            )

        if not isinstance(column, int) or column < 0:
            raise ValidationError(
                f"Column index must be a non‑negative integer, got {column!r}.",
                details={"column": column},
                hint="Column indices are 0‑based.  Use 0 for the first column.",
            )

        if not data:
            raise ValidationError(
                "Data must not be empty.",
                hint="Provide at least one value, e.g. [1.0, 2.0, 3.0].",
            )

        if len(data) > DEFAULT_MAX_ROWS:
            raise ValidationError(
                f"Data has {len(data)} rows — maximum is {DEFAULT_MAX_ROWS}.",
                details={"row_count": len(data), "max_rows": DEFAULT_MAX_ROWS},
                hint="Reduce the dataset size or split it across multiple columns.",
            )

        # ── 2. Locate worksheet ───────────────────────────────────────
        import originpro as op
        wks = _find_worksheet(op, worksheet_name)

        # Ensure the requested column exists (auto-expand the worksheet).
        try:
            while column >= len(wks.cols):
                wks.add_col()
        except Exception:
            raise ToolExecutionError(
                f"Unable to expand worksheet to column {column}.",
                details={"column": column, "existing_cols": len(wks.cols)},
                hint="The column index may be too large for this worksheet.",
            )

        # ── 3. Populate the column ────────────────────────────────────
        axis_code = _AXIS_TO_CODE[axis]

        try:
            wks.from_list(
                column,
                list(data),
                lname=long_name,
                units=units,
                comments=comments,
                axis=axis_code,
            )
        except Exception as exc:
            raise ToolExecutionError.from_exc(
                exc,
                hint="The originpro from_list() call failed.  Check that the data values are all numeric.",
            )

        # ── 4. Build response ─────────────────────────────────────────
        result = {
            "worksheet": getattr(wks, "name", ""),
            "column": column,
            "row_count": len(data),
            "long_name": long_name,
            "units": units,
        }
        return format_response(True, data=result)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ToolExecutionError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as e:
        return format_response(
            False, error=str(e), hint="An unexpected error occurred while setting column data.",
        )


# ---------------------------------------------------------------------------
# A3: import_csv
# ---------------------------------------------------------------------------

def import_csv(
    file_path: str = "",
    worksheet_name: str = "",
    start_row: int = 0,
    end_row: int = 0,
) -> dict:
    """Import data from a CSV (or TXT / DAT) file into an Origin worksheet.

    Uses Origin's built‑in Data Connector for robust parsing with automatic
    delimiter and header detection.

    Args:
        file_path: Absolute or workspace‑relative path to the CSV file.
        worksheet_name: Target worksheet (empty = create a new sheet).
        start_row: Starting row for partial import (1‑based; 0 = all rows).
        end_row: Ending row for partial import (1‑based, inclusive; 0 = all).

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``worksheet``, ``file``, ``row_count``, ``column_count``,
        and a ``columns`` list with ``{name, long_name}`` per column.
    """
    try:
        ensure_origin()

        # ── 1. Validate file path ─────────────────────────────────────
        if not file_path:
            raise ValidationError(
                "File path must not be empty.",
                hint="Provide the path to a CSV, TXT, or DAT file.",
            )

        resolved = safe_path(file_path)

        if not os.path.isfile(resolved):
            raise ValidationError(
                f"File not found: {resolved}",
                details={"file_path": resolved},
                hint=f"Check that the file exists at '{resolved}'.",
            )

        _, ext = os.path.splitext(resolved)
        if ext.lower() not in _CSV_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file extension '{ext}'.  "
                f"Accepted extensions: {', '.join(sorted(_CSV_EXTENSIONS))}.",
                details={"file_path": resolved, "extension": ext},
                hint="For CSV import use .csv, .txt, or .dat files.",
            )

        # Validate row range if partial import requested.
        partial = start_row > 0 or end_row > 0
        if partial:
            if start_row < 0:
                raise ValidationError(
                    f"start_row must be >= 0, got {start_row}.",
                    details={"start_row": start_row},
                    hint="Use 0 for all rows, or a positive 1‑based row number.",
                )
            if end_row < 0:
                raise ValidationError(
                    f"end_row must be >= 0, got {end_row}.",
                    details={"end_row": end_row},
                    hint="Use 0 for all rows, or a positive 1‑based row number.",
                )
            if end_row > 0 and start_row > end_row:
                raise ValidationError(
                    f"start_row ({start_row}) cannot exceed end_row ({end_row}).",
                    details={"start_row": start_row, "end_row": end_row},
                    hint="Swap the values so start_row <= end_row.",
                )

        # ── 2. Get or create worksheet ────────────────────────────────
        import originpro as op

        if worksheet_name:
            wks = _find_worksheet(op, worksheet_name)
        else:
            wks = op.new_sheet()

        # ── 3. Import the file ────────────────────────────────────────
        if partial:
            # Use Connector for fine‑grained row selection.
            selrows = f"{start_row}:{end_row}" if end_row > 0 else f"{start_row}:0"
            try:
                conn = op.Connector(wks, dctype="csv")
                conn.import_file(resolved, selrows=selrows)
            except Exception as exc:
                raise ToolExecutionError.from_exc(
                    exc,
                    hint=(
                        "Partial CSV import failed.  Verify the row range is "
                        "within the file's row count, or try importing the "
                        "whole file (start_row=0, end_row=0)."
                    ),
                )
        else:
            try:
                wks.from_file(resolved)
            except Exception as exc:
                raise ToolExecutionError.from_exc(
                    exc,
                    hint=(
                        "CSV import failed.  Check that the file is well‑formed "
                        "and that Origin can read it (permissions, encoding, etc.)."
                    ),
                )

        # ── 4. Build response ─────────────────────────────────────────
        # wks.cols may return an int (column count) in some originpro
        # versions instead of a sequence — guard against both cases.
        try:
            col_count = len(wks.cols)
        except (TypeError, AttributeError):
            col_count = wks.cols if isinstance(wks.cols, int) else 0

        # Determine row count from the first non‑virtual column.
        row_count = 0
        if col_count > 0:
            try:
                col_data = wks.cols[0].get_data()
                row_count = len(col_data) if col_data else 0
            except Exception:
                pass

        columns = []
        for i in range(col_count):
            col = wks.cols[i]
            col_info: dict[str, str] = {
                "name": getattr(col, "name", f"Col({i})"),
                "long_name": "",
            }
            try:
                col_info["long_name"] = col.get_long_name() or ""
            except Exception:
                pass
            columns.append(col_info)

        result: dict[str, Any] = {
            "worksheet": getattr(wks, "name", ""),
            "file": resolved,
            "row_count": row_count,
            "column_count": col_count,
            "columns": columns,
        }
        return format_response(True, data=result)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ToolExecutionError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as e:
        return format_response(
            False, error=str(e), hint="An unexpected error occurred during CSV import.",
        )


# ---------------------------------------------------------------------------
# A4: get_column_info
# ---------------------------------------------------------------------------

def get_column_info(worksheet_name: str = "") -> dict:
    """Return detailed metadata for every column in a worksheet.

    Args:
        worksheet_name: Target worksheet (empty = active sheet).

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``worksheet``, ``column_count``, and a ``columns`` list where each
        entry has ``index``, ``name``, ``long_name``, ``units``,
        ``comments``, and ``axis``.
    """
    try:
        ensure_origin()
        import originpro as op

        wks = _find_worksheet(op, worksheet_name)

        col_count = len(wks.cols) if wks.cols else 0
        columns: list[dict[str, Any]] = []

        for i in range(col_count):
            col = wks.cols[i]
            col_info: dict[str, Any] = {
                "index": i,
                "name": getattr(col, "name", f"Col({i})"),
                "long_name": "",
                "units": "",
                "comments": "",
                "axis": "",
            }

            # Safely extract optional metadata — each getter may not exist
            # on older originpro versions or graph‑type pages.
            try:
                col_info["long_name"] = col.get_long_name() or ""
            except Exception:
                pass
            try:
                col_info["units"] = col.get_units() or ""
            except Exception:
                pass
            try:
                col_info["comments"] = col.get_comments() or ""
            except Exception:
                pass

            col_info["axis"] = _get_column_axis(col)

            columns.append(col_info)

        result = {
            "worksheet": getattr(wks, "name", ""),
            "column_count": col_count,
            "columns": columns,
        }
        return format_response(True, data=result)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as e:
        return format_response(
            False, error=str(e), hint="An unexpected error occurred while reading column info.",
        )
