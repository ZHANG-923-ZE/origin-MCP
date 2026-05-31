"""MCP customisation tools: modify chart appearance in existing Origin graphs.

Six tools that operate on in-memory Origin graph windows to set axis formatting,
labels, titles, plot styles, legends, and text annotations.  All follow the
standard tool architecture:

    ensure_origin() → import originpro → validate → operate → format_response
"""

from __future__ import annotations

from typing import Any

from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.constants import (
    COLORMAPS,
    LINE_STYLES,
    SCALE_TYPES,
)
from mcp_origin.core.errors import (
    OriginNotRunningError,
    ToolExecutionError,
    ValidationError,
)
from mcp_origin.utils import format_response, parse_color

# ---------------------------------------------------------------------------
# Axis scale codes from the Origin COM enumeration (AXISSCALE).
# ---------------------------------------------------------------------------
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

# Valid grid line styles for axis formatting.
_GRID_STYLES: dict[str, int] = {
    "solid": 0,
    "dash": 1,
    "dot": 2,
    "dash_dot": 3,
    "dash_dot_dot": 4,
    "short_dash": 5,
    "short_dot": 6,
    "none": 7,
}

# Legend position mapping: user-facing names → Origin internal placement codes.
_LEGEND_POSITIONS: dict[str, int] = {
    "top-right": 0,
    "top-left": 1,
    "bottom-right": 2,
    "bottom-left": 3,
    "center": 4,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_graph(op: Any, name: str) -> Any:
    """Resolve a graph page by name, or return the active graph.

    Args:
        op: The originpro module (already imported).
        name: Graph page short-name.  An empty string means "active graph".

    Returns:
        The originpro graph page object.

    Raises:
        ValidationError: No graph matching *name* could be found.
    """
    if not name:
        g = op.find_sheet("g")
        if g is None:
            raise ValidationError(
                "No active graph page.  Create a graph first.",
                hint="Use create_plot() to create a new graph, "
                "or open an existing Origin project with graphs.",
            )
        return g

    g = op.find_sheet("g", name)
    if g is None:
        # Best-effort listing of available graph pages.
        available: list[str] = []
        try:
            for idx in range(len(op.pages)):
                page = op.pages[idx]
                if (
                    hasattr(page, "type")
                    and page.type == "g"
                    and hasattr(page, "name")
                ):
                    available.append(page.name)
        except Exception:
            pass

        hint_msg = f"Graph '{name}' was not found."
        if available:
            hint_msg += f" Available graphs: {', '.join(available)}"
        else:
            hint_msg += " No graph pages are currently open in the project."
        raise ValidationError(
            f"Graph '{name}' not found.",
            details={"graph_name": name, "available": available},
            hint=hint_msg,
        )
    return g


def _get_graph_layer(g: Any, layer_index: int = 0) -> Any:
    """Return a graph layer from a graph page.

    Args:
        g: An originpro graph page object.
        layer_index: 0-based layer index (default ``0``).

    Returns:
        The originpro graph layer object.

    Raises:
        ValidationError: The layer index is out of range.
    """
    try:
        layer_count = len(g)
    except Exception:
        layer_count = 0

    if layer_index < 0 or layer_index >= layer_count:
        raise ValidationError(
            f"Layer index {layer_index} is out of range "
            f"(graph has {layer_count} layer(s)).",
            details={"layer_index": layer_index, "layer_count": layer_count},
            hint=f"Use a value between 0 and {layer_count - 1} inclusive.",
        )
    return g[layer_index]


def _normalize_graph_name(g: Any) -> str:
    """Best-effort extraction of a graph page's short name."""
    try:
        return str(g.name) if g.name else ""
    except Exception:
        try:
            return str(g.get_long_name()) if g.get_long_name() else ""
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# C1: set_axis_format
# ---------------------------------------------------------------------------


def set_axis_format(
    graph_name: str = "",
    axis: str = "x",
    scale_type: str = "",
    from_: float | None = None,
    to: float | None = None,
    increment: float = 0,
    minor_tick_count: int = 1,
    grid: bool = True,
    grid_style: str = "solid",
    grid_color: str = "#E0E0E0",
    tick_direction: str = "in",
) -> dict:
    """Format an axis on an existing Origin graph.

    Args:
        graph_name: Short-name of the graph page.  If empty, the active graph
            is used.
        axis: Which axis to format (``"x"``, ``"y"``, ``"y2"``, ``"z"``).
        scale_type: Axis scale type.  One of :data:`SCALE_TYPES`, or empty to
            leave unchanged.  Examples: ``"linear"``, ``"log10"``, ``"ln"``.
        from_: Axis minimum.  ``None`` means leave unchanged.
        to: Axis maximum.  ``None`` means leave unchanged.
        increment: Major tick increment.  ``0`` means auto.
        minor_tick_count: Number of minor ticks between each major tick.
        grid: Show grid lines (``True``) or hide them (``False``).
        grid_style: Grid line style (``"solid"``, ``"dash"``, ``"dot"``, etc.).
        grid_color: Grid line colour (hex or named colour).
        tick_direction: Tick mark direction (``"in"``, ``"out"``, ``"both"``).

    Returns:
        Standardised response dict with axis formatting details.
    """
    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.  Is OriginPro 2025b installed?",
            tool_name="set_axis_format",
            details=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 1. Validate parameters.
    # ------------------------------------------------------------------
    axis_lower = axis.lower().strip()
    valid_axes = frozenset({"x", "y", "y2", "z"})
    if axis_lower not in valid_axes:
        raise ValidationError(
            f"Unknown axis '{axis}'.",
            details={"axis": axis, "valid": sorted(valid_axes)},
            hint="Choose 'x', 'y', 'y2', or 'z'.",
        )

    if scale_type and scale_type.lower() not in SCALE_TYPES:
        raise ValidationError(
            f"Unknown scale_type '{scale_type}'.",
            details={"scale_type": scale_type, "valid": SCALE_TYPES},
            hint=f"Choose from: {', '.join(SCALE_TYPES)}",
        )

    # Validate tick_direction.
    tick_lower = tick_direction.lower().strip()
    valid_tick_dirs = frozenset({"in", "out", "both"})
    if tick_lower not in valid_tick_dirs:
        raise ValidationError(
            f"Unknown tick_direction '{tick_direction}'.",
            details={"tick_direction": tick_direction, "valid": sorted(valid_tick_dirs)},
            hint="Choose 'in', 'out', or 'both'.",
        )

    # Validate grid_style.
    gs_lower = grid_style.lower().strip()
    if gs_lower not in _GRID_STYLES:
        raise ValidationError(
            f"Unknown grid_style '{grid_style}'.",
            details={"grid_style": grid_style, "valid": sorted(_GRID_STYLES.keys())},
            hint=f"Choose from: {', '.join(sorted(_GRID_STYLES.keys()))}",
        )

    # Parse grid colour.
    hex_grid_color = parse_color(grid_color)

    # ------------------------------------------------------------------
    # 2. Find graph and layer.
    # ------------------------------------------------------------------
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    resolved_name = _normalize_graph_name(g)

    try:
        gl = _get_graph_layer(g, 0)
    except ValidationError:
        raise

    # ------------------------------------------------------------------
    # 3. Apply axis formatting.
    # ------------------------------------------------------------------
    applied_props: list[str] = []
    scale_code: int | None = None

    try:
        ax = gl.axis(axis_lower)
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to access axis '{axis_lower}' on graph layer.",
            tool_name="set_axis_format",
            details={"graph_name": resolved_name, "axis": axis_lower, "error": str(exc)},
        ) from exc

    # Scale type.
    if scale_type:
        scale_code = _SCALE_CODES.get(scale_type.lower())
        if scale_code is not None:
            try:
                ax.scale = scale_code
                applied_props.append("scale")
            except Exception:
                pass

    # Axis range.
    if from_ is not None:
        try:
            ax.from_ = from_
            applied_props.append("from")
        except Exception:
            pass

    if to is not None:
        try:
            ax.to = to
            applied_props.append("to")
        except Exception:
            pass

    # Major tick increment.
    if increment > 0:
        try:
            ax.inc = increment
            applied_props.append("increment")
        except Exception:
            pass

    # Minor ticks.
    if minor_tick_count >= 0:
        try:
            setattr(ax, "minorTickCount", minor_tick_count)
            applied_props.append("minor_ticks")
        except Exception:
            pass

    # Grid.
    try:
        # Toggle grid visibility.
        ax.grid = 1 if grid else 0
        applied_props.append("grid")
    except Exception:
        pass

    # Grid line style.
    try:
        ax.grid_width = _GRID_STYLES[gs_lower]
        applied_props.append("grid_style")
    except Exception:
        pass

    # Grid colour.
    try:
        ax.grid_color = hex_grid_color
        applied_props.append("grid_color")
    except Exception:
        pass

    # Tick direction.
    tick_dir_map: dict[str, str] = {"in": "In", "out": "Out", "both": "Both"}
    try:
        setattr(ax, "tickDirection", tick_dir_map.get(tick_lower, "In"))
        applied_props.append("tick_direction")
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 4. Build and return response.
    # ------------------------------------------------------------------
    range_list: list[float | None] = [from_ if from_ is not None else 0, to if to is not None else 0]
    try:
        range_list[0] = float(ax.from_) if from_ is None else from_
        range_list[1] = float(ax.to) if to is None else to
    except Exception:
        pass

    return format_response(
        True,
        data={
            "graph_name": resolved_name,
            "axis": axis_lower,
            "scale": scale_type.lower() if scale_type else "",
            "scale_code": scale_code,
            "range": range_list,
            "grid": grid,
            "applied_properties": applied_props,
        },
    )


# ---------------------------------------------------------------------------
# C2: set_axis_labels
# ---------------------------------------------------------------------------


def set_axis_labels(
    graph_name: str = "",
    x_label: str = "",
    y_label: str = "",
    y2_label: str = "",
    font_size: int = 18,
    bold: bool = False,
) -> dict:
    """Set axis title labels on an existing Origin graph.

    Args:
        graph_name: Short-name of the graph page.  If empty, the active graph
            is used.
        x_label: X-axis title text.  Empty string means leave unchanged.
        y_label: Y-axis title text.
        y2_label: Secondary Y-axis (right) title text.  Only applies to
            double-Y graphs.
        font_size: Label font size in points.
        bold: Use bold font weight (``True``) or normal (``False``).

    Returns:
        Standardised response dict with label details.
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
            tool_name="set_axis_labels",
            details=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 1. Find graph and layer.
    # ------------------------------------------------------------------
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    resolved_name = _normalize_graph_name(g)

    try:
        gl = _get_graph_layer(g, 0)
    except ValidationError:
        raise

    # ------------------------------------------------------------------
    # 2. Apply axis labels.
    # ------------------------------------------------------------------
    applied_labels: dict[str, str] = {}

    axis_map: list[tuple[str, str]] = [
        ("x", x_label),
        ("y", y_label),
        ("y2", y2_label),
    ]

    for axis_name, label_text in axis_map:
        if not label_text:
            continue

        try:
            ax = gl.axis(axis_name)
        except Exception:
            continue

        try:
            ax.title = label_text
            applied_labels[f"{axis_name}_label"] = label_text
        except Exception:
            continue

        # Apply font properties on the axis title object when available.
        try:
            title_obj = getattr(ax, "title", None)
            if title_obj is not None and hasattr(title_obj, "fontSize"):
                title_obj.fontSize = font_size
            if title_obj is not None and hasattr(title_obj, "bold"):
                title_obj.bold = 1 if bold else 0
        except Exception:
            pass

    return format_response(
        True,
        data={
            "graph_name": resolved_name,
            **applied_labels,
            "font_size": font_size,
            "bold": bold,
        },
    )


# ---------------------------------------------------------------------------
# C3: set_graph_title
# ---------------------------------------------------------------------------


def set_graph_title(
    graph_name: str = "",
    title: str = "",
    font_size: int = 22,
    bold: bool = True,
    position: str = "top",
) -> dict:
    """Set or change the title of an existing Origin graph.

    Args:
        graph_name: Short-name of the graph page.  If empty, the active graph
            is used.
        title: Graph title / long-name text.
        font_size: Title font size in points.
        bold: Use bold font weight (``True``) or normal (``False``).
        position: Title position (``"top"`` or ``"center"``).

    Returns:
        Standardised response dict with title details.
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
            tool_name="set_graph_title",
            details=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 1. Validate parameters.
    # ------------------------------------------------------------------
    pos_lower = position.lower().strip()
    valid_positions = frozenset({"top", "center"})
    if pos_lower not in valid_positions:
        raise ValidationError(
            f"Unknown position '{position}'.",
            details={"position": position, "valid": sorted(valid_positions)},
            hint="Choose 'top' or 'center'.",
        )

    # ------------------------------------------------------------------
    # 2. Find graph.
    # ------------------------------------------------------------------
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    resolved_name = _normalize_graph_name(g)

    # ------------------------------------------------------------------
    # 3. Apply title.
    # ------------------------------------------------------------------
    applied = False

    # Set the graph page's long name (visible title).
    if title:
        try:
            g.lname = title
            applied = True
        except Exception:
            # Fallback: try label property.
            try:
                g.label = title
                applied = True
            except Exception:
                pass

    # Optionally try to set title properties on layer 0 title label.
    try:
        gl = g[0] if len(g) > 0 else None
    except Exception:
        gl = None

    if gl is not None:
        try:
            # Some graph templates expose a title label object.
            tt = gl.label("title") if hasattr(gl, "label") else None
            if tt is not None:
                if hasattr(tt, "text") and title:
                    tt.text = title
                    applied = True
                if hasattr(tt, "fontSize"):
                    tt.fontSize = font_size
                if hasattr(tt, "bold"):
                    tt.bold = 1 if bold else 0
        except Exception:
            pass

    return format_response(
        True,
        data={
            "graph_name": resolved_name,
            "title": title,
            "font_size": font_size,
            "bold": bold,
            "position": pos_lower,
            "applied": applied,
        },
    )


# ---------------------------------------------------------------------------
# C4: set_plot_style
# ---------------------------------------------------------------------------


def set_plot_style(
    graph_name: str = "",
    plot_index: int = 0,
    color: str = "",
    symbol_shape: int = -1,
    symbol_size: int = -1,
    line_width: float = -1.0,
    line_style: str = "",
    fill_color: str = "",
    transparency: int = -1,
    colormap: str = "",
) -> dict:
    """Modify the visual style of a data plot within an existing graph layer.

    All sentinel values (``-1``, ``-1.0``, or empty string) mean "leave
    unchanged" so that callers can pass default-initialised parameters without
    accidentally overriding Origin template defaults.

    Args:
        graph_name: Short-name of the graph page.  If empty, the active graph
            is used.
        plot_index: 0-based index of the plot within the first layer.
        color: Hex or named colour for the plot (e.g. ``"#FF0000"``, ``"red"``).
        symbol_shape: Origin symbol_kind integer (0=square, 1=circle,
            2=up_triangle, 3=diamond, 4=cross, 5=plus, 6=down_triangle).
        symbol_size: Point size in points (positive integer).
        line_width: Line thickness (positive float).
        line_style: One of ``"solid"``, ``"dash"``, ``"dot"``, etc.
        fill_color: Hex or named colour for area/column/bar fill.
        transparency: 0-100 transparency percentage.
        colormap: Name of an Origin built-in colormap palette
            (e.g. ``"Rainbow"``, ``"Viridis"``).  Useful for 3D / contour plots.

    Returns:
        Standardised response dict with a list of modified properties.
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
            tool_name="set_plot_style",
            details=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 1. Validate parameters.
    # ------------------------------------------------------------------
    if line_style and line_style.lower() not in LINE_STYLES:
        raise ValidationError(
            f"Unknown line_style '{line_style}'.",
            details={"line_style": line_style, "valid": sorted(LINE_STYLES.keys())},
            hint=f"Choose from: {', '.join(sorted(LINE_STYLES.keys()))}",
        )

    # Resolve colormap case-insensitively.
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

    # Parse colour parameters.
    hex_color: str = ""
    if color:
        hex_color = parse_color(color)

    hex_fill: str = ""
    if fill_color:
        hex_fill = parse_color(fill_color)

    # ------------------------------------------------------------------
    # 2. Find graph, layer, and plot.
    # ------------------------------------------------------------------
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    resolved_name = _normalize_graph_name(g)

    try:
        gl = _get_graph_layer(g, 0)
    except ValidationError:
        raise

    # Get plot list.
    try:
        plot_list = gl.plot_list()
    except Exception as exc:
        raise ToolExecutionError(
            "Failed to retrieve plot list from graph layer.",
            tool_name="set_plot_style",
            details={"graph_name": resolved_name, "error": str(exc)},
        ) from exc

    if plot_index < 0 or plot_index >= len(plot_list):
        raise ValidationError(
            f"Plot index {plot_index} is out of range "
            f"(layer has {len(plot_list)} plot(s)).",
            details={
                "plot_index": plot_index,
                "plot_count": len(plot_list),
            },
            hint=f"Use a value between 0 and {len(plot_list) - 1} inclusive.",
        )

    p = plot_list[plot_index]
    modified: list[str] = []

    # ------------------------------------------------------------------
    # 3. Apply style properties (sentinel-aware).
    # ------------------------------------------------------------------
    if hex_color:
        try:
            p.color = hex_color
            modified.append("color")
        except Exception:
            pass

    if symbol_shape >= 0:
        try:
            p.symbol_kind = symbol_shape
            modified.append("symbol_shape")
        except Exception:
            pass

    if symbol_size > 0:
        try:
            p.symbol_size = symbol_size
            modified.append("symbol_size")
        except Exception:
            pass

    if line_width > 0:
        try:
            p.line_width = line_width
            modified.append("line_width")
        except Exception:
            pass

    if line_style:
        style_code = LINE_STYLES.get(line_style.lower())
        if style_code is not None:
            try:
                p.line_style = style_code
                modified.append("line_style")
            except Exception:
                pass

    if hex_fill:
        try:
            p.fill_color = hex_fill
            modified.append("fill_color")
        except Exception:
            pass

    if transparency >= 0:
        try:
            p.transparency = transparency
            modified.append("transparency")
        except Exception:
            pass

    if colormap_resolved:
        try:
            p.colormap = colormap_resolved
            modified.append("colormap")
        except Exception:
            pass

    return format_response(
        True,
        data={
            "graph_name": resolved_name,
            "plot_index": plot_index,
            "modified_properties": modified,
        },
    )


# ---------------------------------------------------------------------------
# C5: set_legend
# ---------------------------------------------------------------------------


def set_legend(
    graph_name: str = "",
    show: bool = True,
    position: str = "top-right",
    font_size: int = 12,
    custom_labels: list[str] | None = None,
) -> dict:
    """Configure the legend on an existing Origin graph.

    Args:
        graph_name: Short-name of the graph page.  If empty, the active graph
            is used.
        show: Show the legend (``True``) or hide it (``False``).
        position: Legend position: ``"top-right"``, ``"top-left"``,
            ``"bottom-right"``, ``"bottom-left"``, or ``"center"``.
        font_size: Legend text font size in points.
        custom_labels: Optional list of strings to rename legend entries
            (index-aligned with plots in the layer).

    Returns:
        Standardised response dict with legend configuration details.
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
            tool_name="set_legend",
            details=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 1. Validate parameters.
    # ------------------------------------------------------------------
    pos_lower = position.lower().strip()
    if pos_lower not in _LEGEND_POSITIONS:
        raise ValidationError(
            f"Unknown legend position '{position}'.",
            details={
                "position": position,
                "valid": sorted(_LEGEND_POSITIONS.keys()),
            },
            hint=f"Choose from: {', '.join(sorted(_LEGEND_POSITIONS.keys()))}",
        )

    if custom_labels is None:
        custom_labels = []

    # ------------------------------------------------------------------
    # 2. Find graph and layer.
    # ------------------------------------------------------------------
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    resolved_name = _normalize_graph_name(g)

    try:
        gl = _get_graph_layer(g, 0)
    except ValidationError:
        raise

    # ------------------------------------------------------------------
    # 3. Configure legend.
    # ------------------------------------------------------------------
    applied_actions: list[str] = []

    # Toggle legend visibility on the layer.
    try:
        gl.legend = 1 if show else 0
        applied_actions.append("visibility")
    except Exception:
        pass

    # Set legend position via the legend label object.
    pos_code = _LEGEND_POSITIONS[pos_lower]
    try:
        # Origin legend is a graph label; try to access it.
        if hasattr(gl, "label"):
            leg = gl.label("legend")
            if leg is not None:
                # Position the legend.
                if hasattr(leg, "position"):
                    leg.position = pos_code
                    applied_actions.append("position")
                # Font size.
                if hasattr(leg, "fontSize"):
                    leg.fontSize = font_size
                    applied_actions.append("font_size")
    except Exception:
        pass

    # Custom labels.
    if custom_labels:
        try:
            plot_list = gl.plot_list()
            for i, label_text in enumerate(custom_labels):
                if i < len(plot_list):
                    plot_list[i].legend = label_text
            if custom_labels:
                applied_actions.append("custom_labels")
        except Exception:
            pass

    return format_response(
        True,
        data={
            "graph_name": resolved_name,
            "legend_shown": show,
            "position": pos_lower,
            "font_size": font_size,
            "custom_labels": custom_labels if custom_labels else [],
            "applied_actions": applied_actions,
        },
    )


# ---------------------------------------------------------------------------
# C6: add_text_annotation
# ---------------------------------------------------------------------------


def add_text_annotation(
    graph_name: str = "",
    text: str = "",
    x: float = 0,
    y: float = 0,
    font_size: int = 12,
    color: str = "#000000",
) -> dict:
    """Add a text annotation / label at a specific (x, y) position on a graph.

    Coordinates are in the graph layer's axis coordinate system.

    Args:
        graph_name: Short-name of the graph page.  If empty, the active graph
            is used.
        text: The annotation text string.
        x: X-coordinate for the annotation anchor.
        y: Y-coordinate for the annotation anchor.
        font_size: Font size in points.
        color: Text colour as a hex string or named colour.

    Returns:
        Standardised response dict with annotation details.
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
            tool_name="add_text_annotation",
            details=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 1. Validate parameters.
    # ------------------------------------------------------------------
    if not text:
        raise ValidationError(
            "Annotation text must not be empty.",
            details={"text": text},
            hint="Provide a non-empty text string for the annotation.",
        )

    hex_color = parse_color(color)

    # ------------------------------------------------------------------
    # 2. Find graph and layer.
    # ------------------------------------------------------------------
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    resolved_name = _normalize_graph_name(g)

    try:
        gl = _get_graph_layer(g, 0)
    except ValidationError:
        raise

    # ------------------------------------------------------------------
    # 3. Add text annotation.
    # ------------------------------------------------------------------
    try:
        # originpro provides gl.add_text() or similar label API.
        # Use label on the graph layer to create a text annotation.
        label = gl.label("T")
        if label is not None:
            label.text = text
            if hasattr(label, "x"):
                label.x = x
            if hasattr(label, "y"):
                label.y = y
            if hasattr(label, "fontSize"):
                label.fontSize = font_size
            if hasattr(label, "color"):
                label.color = hex_color
            annotation_id = getattr(label, "name", "")
        else:
            annotation_id = ""
    except Exception as exc:
        raise ToolExecutionError(
            "Failed to add text annotation to the graph layer.",
            tool_name="add_text_annotation",
            details={
                "graph_name": resolved_name,
                "text": text,
                "x": x,
                "y": y,
                "error": str(exc),
            },
            hint="The graph layer may not support direct text annotations via the originpro API.",
        ) from exc

    return format_response(
        True,
        data={
            "graph_name": resolved_name,
            "text": text,
            "position": [x, y],
            "font_size": font_size,
            "color": hex_color,
            "annotation_id": annotation_id,
        },
    )
