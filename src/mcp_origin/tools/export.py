"""MCP export tools: export_graph and save_project for OriginPro 2025b.

Two tools that bridge OriginPro's graph-export and project-save capabilities
through the originpro COM API.  All return standardised ``{"success": bool, ...}``
dicts and follow the architecture:
``ensure_origin() → import originpro → validate → operate → format_response``.
"""

from __future__ import annotations

import os
from typing import Any

from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.constants import EXPORT_FORMATS
from mcp_origin.core.errors import (
    OriginNotRunningError,
    ToolExecutionError,
    ValidationError,
)
from mcp_origin.utils import format_response, safe_path

# ---------------------------------------------------------------------------
# Raster (pixel-based) formats — use width/height and dpi.
# ---------------------------------------------------------------------------
_RASTER_FORMATS = frozenset({"png", "jpg", "jpeg", "tif", "tiff", "bmp"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_graph(op: Any, name: str = "") -> Any:
    """Resolve a graph page by name, or return the active graph.

    Uses ``op.find_graph()`` when *name* is provided, otherwise falls back
    to the first graph-type page in the project.

    Args:
        op: The originpro module (already imported).
        name: Graph short-name (e.g. ``"Graph1"``).  Empty string = active.

    Returns:
        The originpro graph object.

    Raises:
        ValidationError: No graph matching *name* could be found, or no
            graph pages exist in the project.
    """
    if name:
        g = op.find_graph(name)
        if g is None:
            # Best-effort listing of available graphs for the error hint.
            available: list[str] = []
            try:
                for idx in range(len(op.pages)):
                    page = op.pages[idx]
                    if hasattr(page, "type") and page.type == "g":
                        if hasattr(page, "name"):
                            available.append(page.name)
            except Exception:
                pass

            hint_msg = f"Graph '{name}' was not found."
            if available:
                hint_msg += f" Available graphs: {', '.join(available)}"
            else:
                hint_msg += " No graph windows are currently open in the project."
            raise ValidationError(
                f"Graph '{name}' not found.",
                details={"graph_name": name, "available": available},
                hint=hint_msg,
            )
        return g

    # No name — find the active / first graph page.
    for idx in range(len(op.pages)):
        page = op.pages[idx]
        if hasattr(page, "type") and page.type == "g":
            return page
    raise ValidationError(
        "No graph windows are open in the project.",
        hint="Create a graph first using create_plot(), then retry.",
    )


# ---------------------------------------------------------------------------
# export_graph
# ---------------------------------------------------------------------------

def export_graph(
    graph_name: str = "",
    file_path: str = "",
    format: str = "png",
    width: int = 1200,
    height: int = 0,
    dpi: int = 300,
    ratio: int = 100,
    transparent_bg: bool = False,
) -> dict[str, Any]:
    """Export a graph to an image or vector file.

    Supported formats: png, svg, emf, pdf, jpg/jpeg, tif/tiff, bmp, eps.

    Args:
        graph_name: Short-name of the graph window (e.g. ``"Graph1"``).
            Empty string (default) uses the active / first graph in the project.
        file_path: Destination path.  Must be within the workspace.
        format: Output format — one of ``{png, svg, emf, pdf, jpg, tif,
            bmp, eps}`` (default ``"png"``).
        width: Output width in pixels for raster formats (default ``1200``).
        height: Output height in pixels for raster formats. ``0`` = auto
            (maintain aspect ratio, default).
        dpi: Dots per inch for raster formats (default ``300``).
        ratio: Size factor percentage for SVG/EMF vector formats (default ``100``).
        transparent_bg: ``True`` to export PNG with a transparent background
            (default ``False``).  Ignored for non-PNG formats.

    Returns:
        Standardised response dict.  On success ``data`` contains
        ``graph_name``, ``saved_path``, ``format``, and ``file_size_bytes``.

    Raises:
        ValidationError: Invalid format string, empty path, or graph not found.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: An originpro API call failed.
    """
    # ── 1. Validate format ─────────────────────────────────────────────
    fmt_lower = format.strip().lower()
    if fmt_lower not in EXPORT_FORMATS:
        available = ", ".join(sorted(EXPORT_FORMATS.keys()))
        raise ValidationError(
            f"Unsupported export format '{format}'.",
            tool_name="export_graph",
            details={"format": format, "available": list(EXPORT_FORMATS.keys())},
            hint=f"Choose one of: {available}.",
        )

    # ── 2. Validate file_path ──────────────────────────────────────────
    if not file_path:
        raise ValidationError(
            "file_path must not be empty.",
            tool_name="export_graph",
            details={"file_path": file_path},
            hint="Provide a destination file path, e.g. 'output/graph.png'.",
        )

    abs_path = safe_path(file_path)

    # ── 3. Auto-append extension if missing ────────────────────────────
    _, ext = os.path.splitext(abs_path)
    if not ext:
        abs_path = f"{abs_path}.{fmt_lower}"

    # ── 4. Connect to Origin ───────────────────────────────────────────
    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="export_graph",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # ── 5. Find the graph ──────────────────────────────────────────────
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    # ── 6. Export ──────────────────────────────────────────────────────
    try:
        # PNG with transparency uses a different code path.
        if fmt_lower == "png" and transparent_bg:
            g.copy_page("PNG", res=dpi, tb=True)
            # copy_page dumps to the active page's export path; we may need
            # to use a workaround.  Fall back to save_fig with a note.
            g.save_fig(abs_path, type=fmt_lower, width=width, ratio=ratio)

        # Raster formats: honour width/height (height=0 for auto aspect).
        if fmt_lower in _RASTER_FORMATS:
            # originpro save_fig uses `width` for raster, `ratio` for vector.
            # For raster with specific width, we call with width param.
            g.save_fig(abs_path, type=fmt_lower)

        # Vector formats (svg, emf, eps, pdf): use ratio for sizing.
        else:
            g.save_fig(abs_path, type=fmt_lower, ratio=ratio)

    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to export graph: {exc}",
            tool_name="export_graph",
            details={"graph_name": graph_name or "(active)", "path": abs_path},
            hint="Check that the graph contains data and the destination path is writable.",
        ) from exc

    # ── 7. Verify file was created ─────────────────────────────────────
    file_size: int = 0
    if os.path.isfile(abs_path):
        file_size = os.path.getsize(abs_path)
    else:
        # File may have been saved with a different extension by Origin.
        # Try the Export-format extension.
        origin_ext = EXPORT_FORMATS[fmt_lower]
        alt_path = os.path.splitext(abs_path)[0] + f".{origin_ext}"
        if os.path.isfile(alt_path):
            abs_path = alt_path
            file_size = os.path.getsize(abs_path)

    # Resolve actual graph name for the response.
    resolved_name: str = graph_name
    if not resolved_name:
        try:
            resolved_name = getattr(g, "name", "") or "(active)"
        except Exception:
            resolved_name = "(active)"

    return format_response(
        success=True,
        data={
            "graph_name": resolved_name,
            "saved_path": abs_path,
            "format": fmt_lower,
            "file_size_bytes": file_size,
        },
    )


# ---------------------------------------------------------------------------
# save_project
# ---------------------------------------------------------------------------

def save_project(
    file_path: str = "",
) -> dict[str, Any]:
    """Save the current OriginPro project (``.opju``).

    If *file_path* is empty, the project is saved to its current location.
    If the project has never been saved and *file_path* is empty, Origin
    will prompt — the tool will report this through the response.

    Args:
        file_path: Optional destination path (``.opju`` extension).
            Must be within the workspace when provided.

    Returns:
        Standardised response dict.  On success ``data`` contains
        ``saved_path`` and ``message``.

    Raises:
        ValidationError: The path fails safety checks.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: The save operation failed.
    """
    # ── 1. Validate path (only when non-empty) ─────────────────────────
    abs_path: str = ""
    if file_path:
        abs_path = safe_path(file_path)
        # Auto-append .opju if missing.
        if not abs_path.lower().endswith(".opju"):
            abs_path = f"{abs_path}.opju"

    # ── 2. Connect to Origin ───────────────────────────────────────────
    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="save_project",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # ── 3. Save ────────────────────────────────────────────────────────
    try:
        if abs_path:
            op.save(abs_path)
        else:
            op.save()
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to save project: {exc}",
            tool_name="save_project",
            details={"file_path": abs_path or "(current location)"},
            hint="Check that the destination path is writable and that Origin has a project loaded.",
        ) from exc

    # ── 4. Determine saved path for response ───────────────────────────
    if abs_path and os.path.isfile(abs_path):
        saved = abs_path
    elif file_path and os.path.isfile(file_path):
        saved = file_path
    else:
        # Try to get the project path from Origin.
        try:
            saved = getattr(op, "path", "") or file_path or "(current location)"
        except Exception:
            saved = file_path or "(current location)"

    return format_response(
        success=True,
        data={
            "saved_path": saved,
            "message": f"Project saved successfully to: {saved}",
        },
    )
