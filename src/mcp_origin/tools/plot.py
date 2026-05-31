"""MCP plotting tools: unified ``create_plot`` engine for OriginPro 2025b.

A single function routes a human-readable ``plot_type`` string to any of the 52+
Origin plot types across 2D, 3D, contour/heatmap, and multi-panel dimensions.
The actual ``@mcp.tool()`` registration happens in ``server.py`` (Phase 3, T8).

Supported plot types (52 total)
--------------------------------
**2D Basic** (7): line, scatter, line_symbol, column, bar, area, pie
**2D Stacked** (3): stack_column, stack_bar, stack_area
**2D Statistical** (4): box, histogram, error_bar, x_error_bar
**2D Advanced** (7): bubble, color_bubble, float_bar, high_low_close,
  ohlc_candlestick, vector_xyxy, vector_xyam
**2D Specialized** (8): polar, polar_xr_theta, ternary, smith_chart, windrose,
  dendrogram, waterfall_2d, double_y
**3D** (11): 3d_scatter, 3d_trajectory, 3d_surface, 3d_mesh, 3d_wireframe,
  3d_bars, 3d_ribbons, 3d_walls, 3d_waterfall, 3d_vector, 3d_scatter_error
**Contour / Heatmap** (7): contour, contour_filled, contour_line, contour_gray,
  heatmap, image, ternary_contour
**Multi-Panel** (5): multi_panel_2v, multi_panel_2h, multi_panel_4,
  multi_panel_9, multi_panel_stack
"""

from __future__ import annotations

from typing import Any

from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.constants import (
    COLORMAPS,
    LINE_STYLES,
    SCALE_TYPES,
    get_plot_info,
)
from mcp_origin.core.errors import (
    OriginNotRunningError,
    ToolExecutionError,
    ValidationError,
)
from mcp_origin.utils import format_response, parse_color

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Plot types whose originpro API supports error-bar columns.
_ERROR_SUPPORTED_TYPES = frozenset(
    {"error_bar", "x_error_bar", "line", "scatter", "line_symbol"}
)

# Mapping of user-facing scale-type strings → Origin integer axis-scale codes.
# Codes are from the Origin C/COM documentation (AXISSCALE enumeration).
_SCALE_CODES: dict[str, int] = {
    "linear": 0,
    "log10": 2,
    "ln": 3,
    "log2": 4,
    "probability": 5,
    "probit": 6,
    "reciprocal": 7,
    "offset_reciprocal": 8,
    "logit": 9,
}

# Default colours for each dimension when none is supplied.
_DIM_DEFAULT_COLORS: dict[str, str] = {
    "2d": "#0000ff",
    "3d": "",  # use colormap
    "contour": "",  # use colormap
    "panel": "#0000ff",
    "special": "#0000ff",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_worksheet(op: Any, name: str) -> Any:
    """Resolve a worksheet by name, or return the active worksheet.

    Pattern mirrors :func:`mcp_origin.tools.data._find_worksheet`.

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
                "No active worksheet available. "
                "Create or open a worksheet first.",
                hint="Use create_worksheet() to create a new sheet, "
                "or open an existing Origin project.",
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
    """Best-effort listing of open worksheet names in the Origin project."""
    names: list[str] = []
    try:
        for idx in range(len(op.pages)):
            page = op.pages[idx]
            if (
                hasattr(page, "type")
                and page.type == "w"
                and hasattr(page, "name")
            ):
                names.append(page.name)
    except Exception:
        pass
    return names


def _apply_style(
    plot: Any,
    color: str = "",
    symbol_shape: int = -1,
    symbol_size: int = -1,
    line_width: float = -1.0,
    line_style: str = "",
    fill_color: str = "",
    transparency: int = -1,
    colormap: str = "",
) -> None:
    """Apply style parameters to a single plot object.

    Empty strings and sentinel values (``-1`` / ``-1.0``) are treated as
    "skip" so that callers can pass default-initialised parameters without
    accidentally overriding Origin template defaults.

    Args:
        plot: An originpro plot object (returned by ``gl.add_plot()``).
        color: Hex colour string (e.g. ``"#ff0000"``).
        symbol_shape: Origin symbol_kind integer (0-6).
        symbol_size: Point size in points.
        line_width: Line thickness.
        line_style: One of the keys in :data:`LINE_STYLES`.
        fill_color: Hex colour for area/column/bar fill.
        transparency: 0-100 transparency percentage.
        colormap: Name of an Origin built-in colormap palette.
    """
    if color:
        try:
            plot.color = color
        except Exception:
            pass

    if symbol_shape >= 0:
        try:
            plot.symbol_kind = symbol_shape
        except Exception:
            pass

    if symbol_size > 0:
        try:
            plot.symbol_size = symbol_size
        except Exception:
            pass

    if line_width > 0:
        try:
            plot.line_width = line_width
        except Exception:
            pass

    if line_style and line_style in LINE_STYLES:
        try:
            plot.line_style = LINE_STYLES[line_style]
        except Exception:
            pass

    if fill_color:
        try:
            plot.fill_color = fill_color
        except Exception:
            pass

    if transparency >= 0:
        try:
            plot.transparency = transparency
        except Exception:
            pass

    if colormap:
        try:
            plot.colormap = colormap
        except Exception:
            pass


def _add_single_plot(
    gl: Any,
    wks: Any,
    plot_type_id: int | None,
    x_col: int,
    y_col: int,
    error_col: int = -1,
    is_x_error: bool = False,
    z_col: int = -1,
) -> Any:
    """Add a single data plot to a graph layer.

    Args:
        gl: Graph layer object (``g[0]``).
        wks: Origin worksheet.
        plot_type_id: Origin numeric plot type ID (``None`` means template default).
        x_col: 0-based X column index.
        y_col: 0-based Y column index.
        error_col: 0-based error-bar column index (-1 = none).
        is_x_error: If ``True``, use ``colxerr``; otherwise ``colyerr``.
        z_col: 0-based Z column index (-1 = none, for 3D/contour).

    Returns:
        The originpro plot object.
    """
    kwargs: dict[str, Any] = {"coly": y_col, "colx": x_col}

    if plot_type_id is not None:
        kwargs["type"] = plot_type_id

    if error_col >= 0:
        if is_x_error:
            kwargs["colxerr"] = error_col
        else:
            kwargs["colyerr"] = error_col

    if z_col >= 0:
        kwargs["colz"] = z_col

    return gl.add_plot(wks, **kwargs)


def _set_axis_properties(
    gl: Any,
    scale_x: str = "linear",
    scale_y: str = "linear",
    x_label: str = "",
    y_label: str = "",
) -> None:
    """Set axis scale types and labels on a graph layer.

    Rescale is called **first** to fit axis ranges to the data.  Non‑default
    scale types are then applied.  The default ``"linear"`` scale is **not**
    explicitly written because setting ``axis.scale`` in Origin COM can
    reset the axis range, undoing the previous rescale.

    Args:
        gl: Graph layer object.
        scale_x: X-axis scale type (key from :data:`SCALE_TYPES`).
        scale_y: Y-axis scale type (key from :data:`SCALE_TYPES`).
        x_label: X-axis title.
        y_label: Y-axis title.
    """
    # ── 1. Rescale first — snaps axis ranges to the actual data. ──────
    try:
        gl.rescale()
    except Exception:
        pass

    # ── 2. Only write non‑linear scale codes ──────────────────────────
    #     Writing ``axis.scale = 0`` (linear) is a no‑op from the user's
    #     perspective but CAN reset axis ranges inside Origin COM, so we
    #     skip it entirely.
    if scale_x != "linear":
        x_code = _SCALE_CODES.get(scale_x)
        if x_code is not None:
            try:
                gl.axis("x").scale = x_code
            except Exception:
                pass

    if scale_y != "linear":
        y_code = _SCALE_CODES.get(scale_y)
        if y_code is not None:
            try:
                gl.axis("y").scale = y_code
            except Exception:
                pass

    # ── 3. Set labels last — they don't affect axis range. ────────────
    if x_label:
        try:
            gl.axis("x").title = x_label
        except Exception:
            pass

    if y_label:
        try:
            gl.axis("y").title = y_label
        except Exception:
            pass

    # Only set a non‑default scale type.  Writing ``scale = 0`` (linear)
    # to a template that already uses linear axes can trigger a COM-level
    # axis‑reset that discards the rescaled data range.
    if scale_x != "linear":
        x_code = _SCALE_CODES.get(scale_x)
        if x_code is not None:
            try:
                gl.axis("x").scale = x_code
            except Exception:
                pass

    if scale_y != "linear":
        y_code = _SCALE_CODES.get(scale_y)
        if y_code is not None:
            try:
                gl.axis("y").scale = y_code
            except Exception:
                pass

    # Set axis labels after rescale and scale-type changes.
    # Labels are cosmetic and do not affect data range.
    if x_label:
        try:
            gl.axis("x").title = x_label
        except Exception:
            pass

    if y_label:
        try:
            gl.axis("y").title = y_label
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main plot-creation function
# ---------------------------------------------------------------------------


def create_plot(
    plot_type: str,
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    y_cols: list[int] | None = None,
    z_col: int = -1,
    error_col: int = -1,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    color: str = "",
    colors: list[str] | None = None,
    colormap: str = "",
    symbol_shape: int = 1,
    symbol_size: int = 8,
    line_width: float = 1.5,
    line_style: str = "solid",
    fill_color: str = "",
    transparency: int = 0,
    scale_x: str = "linear",
    scale_y: str = "linear",
    template: str = "",
    group_by_col: int = -1,
) -> dict:
    """Create a graph in OriginPro using the unified plotting engine.

    Routes a human-readable ``plot_type`` string to the correct Origin template,
    plot-type ID, and dimension-aware construction logic.  Supports all 52+
    Origin 2025b plot types (see the module docstring for the full list).

    Args:
        plot_type: Case-insensitive plot type key (e.g. ``"scatter"``,
            ``"3d_surface"``, ``"contour"``, ``"multi_panel_4"``).
        worksheet_name: Name of the worksheet containing the data.  If empty,
            the active worksheet is used.
        x_col: 0-based X column index (default ``0``).
        y_col: 0-based Y column index (default ``1``).
        y_cols: List of 0-based Y column indices for multi-curve plots.
            When provided, each column is added as a separate curve.
        z_col: 0-based Z column index for 3D / contour plots (default ``-1``
            meaning unused).  **Required** for ``"3d"`` / ``"contour"`` types.
        error_col: 0-based error-bar column index (default ``-1`` meaning
            unused).  Only honoured for types that support error bars:
            ``error_bar``, ``x_error_bar``, ``line``, ``scatter``, ``line_symbol``.
        title: Graph long-name / title.
        x_label: X-axis label text.
        y_label: Y-axis label text.
        color: Single hex colour or named colour string (e.g. ``"#FF0000"``,
            ``"red"``).  Applied to the first / only plot.
        colors: List of colour strings for multi-curve plots.  Index-aligned
            with ``y_cols``.
        colormap: Name of an Origin built-in colormap (e.g. ``"Rainbow"``,
            ``"Fire"``, ``"Viridis"``).  Case-insensitive.  Used for 3D and
            contour plots.
        symbol_shape: Origin symbol_kind integer (0=square, 1=circle,
            2=up_triangle, 3=diamond, 4=cross, 5=plus, 6=down_triangle).
        symbol_size: Point size in points (default ``8``).
        line_width: Line thickness (default ``1.5``).
        line_style: One of ``"solid"``, ``"dash"``, ``"dot"``, ``"dash_dot"``,
            ``"dash_dot_dot"``, ``"short_dash"``, ``"short_dot"``.
        fill_color: Hex colour for area/column/bar fill.
        transparency: 0-100 transparency percentage (0 = fully opaque).
        scale_x: X-axis scale type (one of :data:`SCALE_TYPES`).
        scale_y: Y-axis scale type (one of :data:`SCALE_TYPES`).
        template: Override the Origin graph template name.  If empty, the
            template mapped from ``plot_type`` is used.
        group_by_col: 0-based column index for grouping data series.  When
            ``>= 0`` the column's distinct values split the data into separate
            plots.  Full multi-curve / grouped logic is implemented in the
            layered tools (Phase 3, T7); this parameter is reserved for those.

    Returns:
        Standardised response dict with ``success`` (bool) and ``data``
        containing:

        * ``graph_name`` — Origin short-name of the created graph window.
        * ``template_used`` — Template name that was applied.
        * ``plot_type`` — Resolved plot-type key.
        * ``dimension`` — Dimension category (``"2d"``, ``"3d"``, ``"contour"``,
          ``"panel"``).
        * ``layer_count`` — Number of graph layers.
        * ``plot_count`` — Number of data plots added.
        * ``columns_used`` — Dict of ``{x, y, z, error}`` column indices
          (``None`` for unused).

    Raises:
        ValidationError: Invalid ``plot_type``, missing required columns,
            or unsupported parameter combinations.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: An originpro API call failed at runtime.

    Example:
        >>> result = create_plot("scatter", worksheet_name="Data1",
        ...                      x_col=0, y_col=1, color="red",
        ...                      title="My Scatter", x_label="Time (s)")
        >>> result["success"]
        True
    """
    # Normalise mutable-default-style parameters.
    if y_cols is None:
        y_cols = []
    if colors is None:
        colors = []

    # ------------------------------------------------------------------
    # 0. Ensure Origin is running, then import originpro lazily.
    # ------------------------------------------------------------------
    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.  Is OriginPro 2025b installed?",
            tool_name="create_plot",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # ------------------------------------------------------------------
    # 1. Validate plot_type.
    # ------------------------------------------------------------------
    try:
        info = get_plot_info(plot_type)
    except KeyError as exc:
        raise ValidationError(
            str(exc),
            tool_name="create_plot",
            details={"plot_type": plot_type},
            hint="Choose one of the 52+ supported plot types listed in the docstring.",
        ) from exc

    dim = info["dim"]
    plot_type_id = info.get("id")

    # ------------------------------------------------------------------
    # 2. Validate other enum-type parameters.
    # ------------------------------------------------------------------
    if scale_x not in SCALE_TYPES:
        raise ValidationError(
            f"Unknown scale_x '{scale_x}'.",
            details={"scale_x": scale_x, "valid": SCALE_TYPES},
            hint=f"Choose from: {', '.join(SCALE_TYPES)}",
        )
    if scale_y not in SCALE_TYPES:
        raise ValidationError(
            f"Unknown scale_y '{scale_y}'.",
            details={"scale_y": scale_y, "valid": SCALE_TYPES},
            hint=f"Choose from: {', '.join(SCALE_TYPES)}",
        )
    if line_style not in LINE_STYLES:
        raise ValidationError(
            f"Unknown line_style '{line_style}'.",
            details={"line_style": line_style, "valid": sorted(LINE_STYLES.keys())},
            hint=f"Choose from: {', '.join(sorted(LINE_STYLES.keys()))}",
        )

    # Validate colormap name (case-insensitive).
    colormap_resolved: str = ""
    if colormap:
        cm_lower = colormap.lower()
        match = None
        for cm in COLORMAPS:
            if cm.lower() == cm_lower:
                match = cm
                break
        if match is None:
            raise ValidationError(
                f"Unknown colormap '{colormap}'.",
                details={"colormap": colormap, "valid": COLORMAPS},
                hint=f"Choose from: {', '.join(COLORMAPS)}",
            )
        colormap_resolved = match

    # ------------------------------------------------------------------
    # 3. Validate dimension-specific column requirements.
    # ------------------------------------------------------------------
    if dim in ("3d", "contour") and z_col < 0:
        raise ValidationError(
            f"'{plot_type}' requires a Z column.  Set z_col >= 0.",
            details={"plot_type": plot_type, "dim": dim, "z_col": z_col},
            hint="Pass z_col=<0-based index> to specify the Z data column.",
        )

    if error_col >= 0 and plot_type.lower() not in _ERROR_SUPPORTED_TYPES:
        raise ValidationError(
            f"Plot type '{plot_type}' does not support error bars.",
            details={
                "plot_type": plot_type,
                "error_col": error_col,
                "supported_types": sorted(_ERROR_SUPPORTED_TYPES),
            },
            hint=f"Error bars are supported for: {', '.join(sorted(_ERROR_SUPPORTED_TYPES))}",
        )

    # ------------------------------------------------------------------
    # 4. Find worksheet.
    # ------------------------------------------------------------------
    try:
        wks = _find_worksheet(op, worksheet_name)
    except ValidationError:
        raise

    # ------------------------------------------------------------------
    # 5. Parse colour parameters.
    # ------------------------------------------------------------------
    hex_color: str = ""
    if color:
        hex_color = parse_color(color)

    hex_colors: list[str] = []
    if colors:
        for c in colors:
            hex_colors.append(parse_color(c))

    # ------------------------------------------------------------------
    # 6. Create the graph page.
    # ------------------------------------------------------------------
    use_template = template or info["template"]
    graph_title = title or f"{plot_type} plot"

    try:
        g = op.new_graph(template=use_template, lname=graph_title)
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to create graph with template '{use_template}'.",
            tool_name="create_plot",
            details={"template": use_template, "error": str(exc)},
            hint="Check that the template name is correct and Origin is responsive.",
        ) from exc

    try:
        graph_name = g.name
    except Exception:
        graph_name = ""

    # Count layers.
    try:
        num_layers = len(g)
    except Exception:
        num_layers = 0

    # ------------------------------------------------------------------
    # 7. Add plots according to dimension.
    # ------------------------------------------------------------------
    plots_added: list[Any] = []

    if dim == "2d":
        # --- Single layer, possibly multi-curve. ---
        gl = g[0]
        target_y_cols = y_cols if y_cols else [y_col]
        is_x_error = (plot_type.lower() == "x_error_bar")

        for i, yc in enumerate(target_y_cols):
            # Determine colour for this curve.
            curve_color = ""
            if i < len(hex_colors):
                curve_color = hex_colors[i]
            elif hex_color and i == 0:
                curve_color = hex_color
            elif not hex_colors and not hex_color:
                curve_color = _DIM_DEFAULT_COLORS.get(dim, "")

            # Build and add the plot.
            err = error_col if plot_type.lower() in _ERROR_SUPPORTED_TYPES else -1
            p = _add_single_plot(
                gl,
                wks,
                plot_type_id=plot_type_id,
                x_col=x_col,
                y_col=yc,
                error_col=err,
                is_x_error=is_x_error,
            )
            plots_added.append(p)

            # Apply styles.
            _apply_style(
                p,
                color=curve_color,
                symbol_shape=symbol_shape,
                symbol_size=symbol_size,
                line_width=line_width,
                line_style=line_style,
                fill_color=fill_color,
                transparency=transparency,
            )

        # Axis properties on the single 2D layer.
        _set_axis_properties(gl, scale_x, scale_y, x_label, y_label)

    elif dim in ("3d", "contour"):
        # --- Single 3D / contour layer. ---
        gl = g[0]

        p = _add_single_plot(
            gl,
            wks,
            plot_type_id=plot_type_id,
            x_col=x_col,
            y_col=y_col,
            z_col=z_col,
        )
        plots_added.append(p)

        # 3D / contour styles — colormap is primary; symbol/line less relevant.
        _apply_style(
            p,
            color=hex_color,
            symbol_shape=symbol_shape,
            symbol_size=symbol_size,
            line_width=line_width,
            line_style=line_style,
            fill_color=fill_color,
            transparency=transparency,
            colormap=colormap_resolved,
        )

        _set_axis_properties(gl, scale_x, scale_y, x_label, y_label)

    elif dim == "panel":
        # --- Multi-panel: template creates N layers. ---
        # For panel types we set axis properties on each layer but
        # do not automatically add data plots (panel layout is driven
        # by the specialised tools in T7).
        for layer_idx in range(num_layers):
            try:
                gl = g[layer_idx]
                _set_axis_properties(gl, scale_x, scale_y, x_label, y_label)
            except Exception:
                pass

    else:
        # "special" or future dimension — best-effort single layer.
        try:
            gl = g[0]
            p = _add_single_plot(
                gl,
                wks,
                plot_type_id=plot_type_id,
                x_col=x_col,
                y_col=y_col,
            )
            plots_added.append(p)
            _apply_style(
                p,
                color=hex_color or _DIM_DEFAULT_COLORS.get(dim, ""),
                symbol_shape=symbol_shape,
                symbol_size=symbol_size,
                line_width=line_width,
                line_style=line_style,
                fill_color=fill_color,
                transparency=transparency,
            )
            _set_axis_properties(gl, scale_x, scale_y, x_label, y_label)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 8. Return metadata.
    # ------------------------------------------------------------------
    return format_response(
        True,
        data={
            "graph_name": graph_name,
            "template_used": use_template,
            "plot_type": plot_type,
            "dimension": dim,
            "layer_count": num_layers,
            "plot_count": len(plots_added),
            "columns_used": {
                "x": x_col,
                "y": y_col,
                "z": z_col if z_col >= 0 else None,
                "error": error_col if error_col >= 0 else None,
            },
        },
    )


# ---------------------------------------------------------------------------
# B2: create_multi_curve_plot
# ---------------------------------------------------------------------------


def create_multi_curve_plot(
    plot_type: str = "line",
    worksheet_name: str = "",
    x_col: int = 0,
    y_cols: list[int] | None = None,
    curve_labels: list[str] | None = None,
    colors: list[str] | None = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    line_width: float = 1.5,
    symbol_size: int = 8,
) -> dict:
    """Create a graph with multiple curves from different Y columns sharing the same X.

    Each entry in ``y_cols`` becomes a separate data plot (curve) in a single
    graph layer.  Colours and legend labels are applied per-curve when provided.

    Args:
        plot_type: 2D plot type key (default ``"line"``).  Must be a valid
            :data:`PLOT_TYPE_MAP` entry with ``dim == "2d"``.
        worksheet_name: Name of the worksheet containing the data.
        x_col: 0-based X column index shared by all curves (default ``0``).
        y_cols: List of 0-based Y column indices (required, min 2 entries).
        curve_labels: Optional legend labels, index-aligned with ``y_cols``.
        colors: Optional colour strings, index-aligned with ``y_cols``.
        title: Graph long-name / title.
        x_label: X-axis label text.
        y_label: Y-axis label text.
        line_width: Line thickness (default ``1.5``).
        symbol_size: Symbol point size (default ``8``).

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``graph_name``, ``template_used``, ``curve_count``, ``columns``
        (``[x_col, ...y_cols]``).

    Raises:
        ValidationError: ``y_cols`` has fewer than 2 entries or ``plot_type``
            is not a recognised 2D type.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: An originpro API call failed.
    """
    if y_cols is None:
        y_cols = []
    if curve_labels is None:
        curve_labels = []
    if colors is None:
        colors = []

    if len(y_cols) < 2:
        raise ValidationError(
            "Need at least 2 Y columns for a multi-curve plot.",
            details={"y_cols": y_cols},
            hint="Provide a list of 2+ Y column indices, e.g. y_cols=[1, 2, 3].",
        )

    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="create_multi_curve_plot",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # Validate plot_type is a recognised 2D type.
    try:
        info = get_plot_info(plot_type)
    except KeyError as exc:
        raise ValidationError(
            str(exc),
            tool_name="create_multi_curve_plot",
            details={"plot_type": plot_type},
            hint="Choose a valid plot type from the module docstring.",
        ) from exc

    if info["dim"] not in ("2d",):
        raise ValidationError(
            f"Multi-curve is only supported for 2D plot types (got '{info['dim']}').",
            details={"plot_type": plot_type, "dim": info["dim"]},
            hint="Use a 2D type like 'line', 'scatter', 'line_symbol', 'column'.",
        )

    # Find worksheet.
    wks = _find_worksheet(op, worksheet_name)

    # Parse colours.
    hex_colors: list[str] = []
    for c in colors:
        hex_colors.append(parse_color(c))

    # Create graph.
    use_template = info["template"]
    try:
        g = op.new_graph(template=use_template, lname=title or f"{plot_type} multi-curve")
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to create graph with template '{use_template}'.",
            tool_name="create_multi_curve_plot",
            details={"template": use_template, "error": str(exc)},
            hint="Check that the template name is correct and Origin is responsive.",
        ) from exc

    try:
        graph_name = g.name
    except Exception:
        graph_name = ""

    plot_type_id = info.get("id")
    gl = g[0]
    plots_added: list[Any] = []

    for i, yc in enumerate(y_cols):
        # Build kwargs for add_plot.
        kwargs: dict[str, Any] = {"coly": yc, "colx": x_col}
        if plot_type_id is not None:
            kwargs["type"] = plot_type_id

        p = gl.add_plot(wks, **kwargs)
        plots_added.append(p)

        # Apply colour if provided.
        if i < len(hex_colors):
            try:
                p.color = hex_colors[i]
            except Exception:
                pass

        # Set legend label if provided.
        if i < len(curve_labels) and curve_labels[i]:
            try:
                p.label = curve_labels[i]
            except Exception:
                pass

        # Apply common styles.
        _apply_style(
            p,
            symbol_size=symbol_size,
            line_width=line_width,
            line_style="solid",
        )

    _set_axis_properties(gl, x_label=x_label, y_label=y_label)

    return format_response(
        True,
        data={
            "graph_name": graph_name,
            "template_used": use_template,
            "curve_count": len(plots_added),
            "columns": [x_col] + list(y_cols),
            "plot_type": plot_type,
        },
    )


# ---------------------------------------------------------------------------
# B3: create_grouped_plot
# ---------------------------------------------------------------------------


def create_grouped_plot(
    plot_type: str = "column",
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    group_col: int = 2,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
) -> dict:
    """Create a grouped plot where data series are split by values in a group column.

    Uses Origin's built-in grouping API (``gl.group()``) to automatically
    partition data and create separate plots for each distinct group value.
    Best suited for column and bar charts with categorical grouping.

    Args:
        plot_type: 2D plot type key (default ``"column"``).  Grouping works
            best with ``"column"`` and ``"bar"`` types.
        worksheet_name: Name of the worksheet containing the data.
        x_col: 0-based X column index (category labels, default ``0``).
        y_col: 0-based Y column index (data values, default ``1``).
        group_col: 0-based column index whose distinct values define groups
            (default ``2``).
        title: Graph long-name / title.
        x_label: X-axis label text.
        y_label: Y-axis label text.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``graph_name``, ``template_used``, ``group_column``,
        ``total_curves`` (plots in layer after grouping).

    Raises:
        ValidationError: ``plot_type`` is not recognised, or the dimension
            does not support grouping.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: An originpro API call failed.
    """
    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="create_grouped_plot",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # Validate plot_type.
    try:
        info = get_plot_info(plot_type)
    except KeyError as exc:
        raise ValidationError(
            str(exc),
            tool_name="create_grouped_plot",
            details={"plot_type": plot_type},
            hint="Choose a valid 2D plot type like 'column' or 'bar'.",
        ) from exc

    if info["dim"] not in ("2d",):
        raise ValidationError(
            f"Grouped plotting requires a 2D plot type (got '{info['dim']}').",
            details={"plot_type": plot_type, "dim": info["dim"]},
            hint="Use 'column' or 'bar' for grouped charts.",
        )

    # Validate group_col.
    if group_col < 0:
        raise ValidationError(
            "group_col must be >= 0.",
            details={"group_col": group_col},
            hint="Provide a valid 0-based column index for grouping.",
        )

    # Find worksheet.
    wks = _find_worksheet(op, worksheet_name)

    # Create graph.
    use_template = info["template"]
    try:
        g = op.new_graph(template=use_template, lname=title or f"grouped {plot_type}")
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to create graph with template '{use_template}'.",
            tool_name="create_grouped_plot",
            details={"template": use_template, "error": str(exc)},
            hint="Check that the template name is correct.",
        ) from exc

    try:
        graph_name = g.name
    except Exception:
        graph_name = ""

    plot_type_id = info.get("id")
    gl = g[0]

    # Enable grouping on the layer — Origin will auto-split data by group_col.
    try:
        gl.group(True, 0, group_col)
    except Exception:
        # Best-effort; some templates may not support grouping.
        pass

    # Add the plot.  Origin's group engine partitions it into sub-plots.
    kwargs: dict[str, Any] = {"coly": y_col, "colx": x_col}
    if plot_type_id is not None:
        kwargs["type"] = plot_type_id

    try:
        gl.add_plot(wks, **kwargs)
    except Exception as exc:
        raise ToolExecutionError(
            "Failed to add grouped plot.",
            tool_name="create_grouped_plot",
            details={"error": str(exc)},
            hint="Check that columns exist and contain compatible data.",
        ) from exc

    # Count plots after grouping.
    try:
        total_curves = len(gl.plots)
    except Exception:
        total_curves = 0

    _set_axis_properties(gl, x_label=x_label, y_label=y_label)

    return format_response(
        True,
        data={
            "graph_name": graph_name,
            "template_used": use_template,
            "group_column": group_col,
            "total_curves": total_curves,
            "plot_type": plot_type,
        },
    )


# ---------------------------------------------------------------------------
# B4: create_multi_panel_plot
# ---------------------------------------------------------------------------


def create_multi_panel_plot(
    worksheet_name: str = "",
    plot_type: str = "line",
    x_col: int = 0,
    y_cols: list[int] | None = None,
    panel_labels: list[str] | None = None,
    layout: str = "vertical",
    rows: int = 1,
    cols: int = 1,
    title: str = "",
) -> dict:
    """Create a multi-panel (subplot) graph with one plot per panel.

    Routes to the correct Origin multi-panel template based on ``layout``,
    then adds one data plot to each panel layer from the corresponding
    Y column in ``y_cols``.

    Args:
        worksheet_name: Name of the worksheet containing the data.
        plot_type: 2D plot type key applied to each panel (default ``"line"``).
        x_col: 0-based X column index shared across all panels (default ``0``).
        y_cols: List of 0-based Y column indices, one per panel (required,
            min 2 entries).
        panel_labels: Optional panel title strings, index-aligned with ``y_cols``.
        layout: Panel arrangement — ``"vertical"``, ``"horizontal"``, or
            ``"grid"``.  ``"grid"`` uses ``rows`` × ``cols``.
        rows: Number of rows for ``"grid"`` layout.
        cols: Number of columns for ``"grid"`` layout.
        title: Graph window long-name / title.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``graph_name``, ``template_used``, ``panels`` (layer count),
        ``layout``.

    Raises:
        ValidationError: ``y_cols`` is empty, ``layout`` is unknown, or
            ``plot_type`` is not a recognized 2D type.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: An originpro API call failed.
    """
    if y_cols is None:
        y_cols = []
    if panel_labels is None:
        panel_labels = []

    if not y_cols:
        raise ValidationError(
            "y_cols must not be empty for a multi-panel plot.",
            details={"y_cols": y_cols},
            hint="Provide at least 2 Y column indices, e.g. y_cols=[1, 2].",
        )

    valid_layouts = frozenset({"vertical", "horizontal", "grid"})
    if layout not in valid_layouts:
        raise ValidationError(
            f"Unknown layout '{layout}'.",
            details={"layout": layout, "valid": sorted(valid_layouts)},
            hint="Choose 'vertical', 'horizontal', or 'grid'.",
        )

    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="create_multi_panel_plot",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # Validate plot_type is a recognised 2D type.
    try:
        info = get_plot_info(plot_type)
    except KeyError as exc:
        raise ValidationError(
            str(exc),
            tool_name="create_multi_panel_plot",
            details={"plot_type": plot_type},
            hint="Choose a valid 2D plot type.",
        ) from exc

    plot_type_id = info.get("id")

    # Determine multi-panel template.
    n_panels = len(y_cols)
    if layout == "vertical":
        # Use the closest available vertical template.
        if n_panels <= 2:
            template_name = "PAN2VERT"
        else:
            # For >2 panels, PAN2VERT creates 2 layers; remaining
            # panels go into extra layers (if Origin auto-expands)
            # but we are limited to available templates.
            template_name = "PAN2VERT"
    elif layout == "horizontal":
        template_name = "PAN2HORIZ"
    elif layout == "grid":
        grid_size = max(rows * cols, 1)
        if grid_size <= 4:
            template_name = "PAN4"
        else:
            template_name = "PAN9"
    else:
        template_name = "PAN2VERT"  # fallback

    # Find worksheet.
    wks = _find_worksheet(op, worksheet_name)

    # Create the multi-panel graph.
    try:
        g = op.new_graph(template=template_name, lname=title or f"multi-panel {plot_type}")
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to create multi-panel graph with template '{template_name}'.",
            tool_name="create_multi_panel_plot",
            details={"template": template_name, "error": str(exc)},
            hint="Check that the template name is correct.",
        ) from exc

    try:
        graph_name = g.name
    except Exception:
        graph_name = ""

    # Determine how many layers the template provides.
    try:
        num_layers = len(g)
    except Exception:
        num_layers = 0

    # Add one plot to each panel/layer.
    plots_added = 0
    for i in range(min(n_panels, num_layers)):
        try:
            gl = g[i]
            kwargs: dict[str, Any] = {"coly": y_cols[i], "colx": x_col}
            if plot_type_id is not None:
                kwargs["type"] = plot_type_id
            gl.add_plot(wks, **kwargs)

            # Set panel label if provided.
            if i < len(panel_labels) and panel_labels[i]:
                try:
                    gl.label = panel_labels[i]
                except Exception:
                    pass

            _set_axis_properties(gl)
            plots_added += 1
        except Exception:
            pass

    # For panels beyond what the template provides, try appending layers.
    for i in range(num_layers, n_panels):
        try:
            gl = g.add_layer()
            kwargs = {"coly": y_cols[i], "colx": x_col}
            if plot_type_id is not None:
                kwargs["type"] = plot_type_id
            gl.add_plot(wks, **kwargs)

            if i < len(panel_labels) and panel_labels[i]:
                try:
                    gl.label = panel_labels[i]
                except Exception:
                    pass

            _set_axis_properties(gl)
            plots_added += 1
        except Exception:
            pass

    return format_response(
        True,
        data={
            "graph_name": graph_name,
            "template_used": template_name,
            "panels": plots_added,
            "layout": layout,
            "plot_type": plot_type,
        },
    )


# ---------------------------------------------------------------------------
# B5: add_plot_to_graph
# ---------------------------------------------------------------------------


def add_plot_to_graph(
    graph_name: str = "",
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    plot_type: str = "line",
    color: str = "",
    symbol_shape: int = 1,
    symbol_size: int = 8,
    line_width: float = 1.5,
) -> dict:
    """Add a new data plot to an existing Origin graph.

    Finds the target graph by name and appends a plot to its first layer (layer 0).

    Args:
        graph_name: Name of the existing graph window (required).  Use the
            short-name shown in Origin's title bar (e.g. ``"Graph1"``).
        worksheet_name: Name of the worksheet containing the data.
        x_col: 0-based X column index (default ``0``).
        y_col: 0-based Y column index (default ``1``).
        plot_type: Plot type key for the new curve (default ``"line"``).
        color: Hex or named colour for the new plot (e.g. ``"red"``).
        symbol_shape: Origin symbol_kind integer (0-6, default ``1`` = circle).
        symbol_size: Point size (default ``8``).
        line_width: Line thickness (default ``1.5``).

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``graph_name``, ``plot_index`` (0-based index of the new plot),
        ``plots_in_layer`` (total plots in layer 0 after addition).

    Raises:
        ValidationError: ``graph_name`` is empty or the graph cannot be found.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: An originpro API call failed.
    """
    if not graph_name:
        raise ValidationError(
            "graph_name must not be empty.",
            details={"graph_name": graph_name},
            hint="Provide the name of an existing graph, e.g. 'Graph1'.",
        )

    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="add_plot_to_graph",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # Validate plot_type.
    try:
        info = get_plot_info(plot_type)
    except KeyError as exc:
        raise ValidationError(
            str(exc),
            tool_name="add_plot_to_graph",
            details={"plot_type": plot_type},
            hint="Choose a valid plot type from the module docstring.",
        ) from exc

    plot_type_id = info.get("id")

    # Find the existing graph.
    g = op.find_graph(graph_name)
    if g is None:
        raise ValidationError(
            f"Graph '{graph_name}' was not found.",
            details={"graph_name": graph_name},
            hint="Check the graph name (use the short-name from Origin's title bar) "
            "and ensure the graph window is open.",
        )

    # Find worksheet.
    wks = _find_worksheet(op, worksheet_name)

    # Parse colour.
    hex_color: str = ""
    if color:
        hex_color = parse_color(color)

    # Add plot to layer 0.
    try:
        gl = g[0]
    except Exception as exc:
        raise ToolExecutionError(
            f"Graph '{graph_name}' has no accessible layer 0.",
            tool_name="add_plot_to_graph",
            details={"graph_name": graph_name, "error": str(exc)},
            hint="The graph may be empty or corrupted.",
        ) from exc

    kwargs: dict[str, Any] = {"coly": y_col, "colx": x_col}
    if plot_type_id is not None:
        kwargs["type"] = plot_type_id

    try:
        p = gl.add_plot(wks, **kwargs)
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to add plot to graph '{graph_name}'.",
            tool_name="add_plot_to_graph",
            details={"graph_name": graph_name, "error": str(exc)},
            hint="Check that the columns exist and contain compatible data.",
        ) from exc

    # Apply styles.
    _apply_style(
        p,
        color=hex_color,
        symbol_shape=symbol_shape,
        symbol_size=symbol_size,
        line_width=line_width,
    )

    # Determine plot index and total plot count.
    try:
        plots_in_layer = len(gl.plots)
        plot_index = plots_in_layer - 1
    except Exception:
        plots_in_layer = 0
        plot_index = -1

    return format_response(
        True,
        data={
            "graph_name": graph_name,
            "plot_index": plot_index,
            "plots_in_layer": plots_in_layer,
        },
    )
