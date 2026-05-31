"""FastMCP server instance and tool registration for OriginPro."""

from mcp.server.fastmcp import FastMCP

from mcp_origin.core.connection import ensure_origin, get_origin_status
from mcp_origin.core.errors import OriginNotRunningError
from mcp_origin.core.constants import PLOT_TYPE_MAP
from mcp_origin.tools.data import create_worksheet, set_column_data, import_csv, get_column_info
from mcp_origin.tools.plot import create_plot, create_multi_curve_plot, create_grouped_plot, create_multi_panel_plot, add_plot_to_graph
from mcp_origin.tools.customize import set_axis_format, set_axis_labels, set_graph_title, set_plot_style, set_legend, add_text_annotation
from mcp_origin.tools.analysis import fit_linear, fit_nonlinear, fit_peak, compute_statistics
from mcp_origin.tools.export import export_graph, save_project
from mcp_origin.tools.project import list_graphs, list_worksheets, get_graph_snapshot

# Create the MCP server instance
mcp = FastMCP(
    name="OriginPro",
    instructions="Origin 2025b Scientific Graphing — 52 plot types, curve fitting, statistics. Drive Origin through natural language.",
)


# ── Meta / System Tools ─────────────────────────────────────────────
@mcp.tool(
    description="Check if Origin's COM server is accessible. Call this first to verify connectivity."
)
def ping() -> dict:
    """Health check — verifies that Origin 2025b COM server is reachable.

    The response includes a differentiated ``origin_status``:
    - ``"connected"`` — Origin is running and COM is available.
    - ``"origin_not_running"`` — originpro is installed but Origin isn't running.
    - ``"originpro_not_installed"`` — the originpro package is missing entirely.
    """
    status = get_origin_status()

    response: dict = {
        "success": status["status"] == "connected",
        "origin_status": status["status"],
        "originpro_installed": status["originpro_installed"],
        "available_plot_types": len(PLOT_TYPE_MAP),
    }

    if not response["success"]:
        response["message"] = {
            "originpro_not_installed": (
                "The originpro Python package is not installed. "
                "Origin 2025b COM automation cannot be used."
            ),
            "origin_not_running": (
                "Origin 2025b is NOT running or its COM server is unavailable."
            ),
        }.get(status["status"], "Origin connectivity unknown.")

        response["hint"] = status["hint"]

        if "origin_install_path" in status:
            response["origin_install_path"] = status["origin_install_path"]
    else:
        response["message"] = "Origin 2025b is running and accessible."

    return response


# ── Data Management Tools ──────────────────────────────────────────

@mcp.tool(
    description="Create a new Origin worksheet. Use this before plotting to prepare a data container."
)
def tool_create_worksheet(name: str = "") -> dict:
    return create_worksheet(name)


@mcp.tool(
    description="Set numeric data into a worksheet column. Can attach long name, units, comments, and axis designation (X/Y/Z/Error/Label/Disregard). Max 10000 rows."
)
def tool_set_column_data(
    worksheet_name: str = "",
    column: int = 0,
    data: list[float] = None,
    long_name: str = "",
    units: str = "",
    comments: str = "",
    axis: str = "Y",
) -> dict:
    return set_column_data(worksheet_name, column, data, long_name, units, comments, axis)


@mcp.tool(
    description="Import data from a CSV/TXT/DAT file into an Origin worksheet. Supports full or partial row import."
)
def tool_import_csv(
    file_path: str = "",
    worksheet_name: str = "",
    start_row: int = 0,
    end_row: int = 0,
) -> dict:
    return import_csv(file_path, worksheet_name, start_row, end_row)


@mcp.tool(
    description="Get metadata for all columns in a worksheet: column names, long names, units, comments, and axis designations."
)
def tool_get_column_info(worksheet_name: str = "") -> dict:
    return get_column_info(worksheet_name)


# ── Plotting Tools ──────────────────────────────────────────────────

@mcp.tool(
    description="""Create ANY scientific plot in Origin 2025b. 52+ plot types supported.

plot_type values:
  2D (line, scatter, line_symbol, column, bar, area, pie, stack_column, stack_bar, stack_area, box, histogram, error_bar, x_error_bar, bubble, color_bubble, float_bar, high_low_close, ohlc_candlestick, vector_xyxy, vector_xyam, polar, polar_xr_theta, ternary, smith_chart, windrose, dendrogram, waterfall_2d, double_y)
  3D (3d_scatter, 3d_trajectory, 3d_surface, 3d_mesh, 3d_wireframe, 3d_bars, 3d_ribbons, 3d_walls, 3d_waterfall, 3d_vector, 3d_scatter_error)
  Contour (contour, contour_filled, contour_line, contour_gray, heatmap, image, ternary_contour)
  Panel (multi_panel_2v, multi_panel_2h, multi_panel_4, multi_panel_9, multi_panel_stack)

For multi-curve: use y_cols=[...] and colors=[...]. For 3D/contour: set z_col. For error bars: set error_col."""
)
def tool_create_plot(
    plot_type: str,
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    y_cols: list[int] = None,
    z_col: int = -1,
    error_col: int = -1,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    color: str = "",
    colors: list[str] = None,
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
    return create_plot(plot_type, worksheet_name, x_col, y_col, y_cols, z_col, error_col, title, x_label, y_label, color, colors, colormap, symbol_shape, symbol_size, line_width, line_style, fill_color, transparency, scale_x, scale_y, template, group_by_col)


@mcp.tool(
    description="Plot multiple Y curves sharing the same X axis. Each curve gets a separate color and legend label."
)
def tool_create_multi_curve_plot(
    plot_type: str = "line",
    worksheet_name: str = "",
    x_col: int = 0,
    y_cols: list[int] = None,
    curve_labels: list[str] = None,
    colors: list[str] = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    line_width: float = 1.5,
    symbol_size: int = 8,
) -> dict:
    return create_multi_curve_plot(plot_type, worksheet_name, x_col, y_cols or [], curve_labels or [], colors or [], title, x_label, y_label, line_width, symbol_size)


@mcp.tool(
    description="Create a grouped column/bar chart where data is grouped by values in a specified column."
)
def tool_create_grouped_plot(
    plot_type: str = "column",
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    group_col: int = 2,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
) -> dict:
    return create_grouped_plot(plot_type, worksheet_name, x_col, y_col, group_col, title, x_label, y_label)


@mcp.tool(
    description="Create a multi-panel (subplot) layout. Choose vertical, horizontal, or grid arrangement. Each panel shows one Y column."
)
def tool_create_multi_panel_plot(
    worksheet_name: str = "",
    plot_type: str = "line",
    x_col: int = 0,
    y_cols: list[int] = None,
    panel_labels: list[str] = None,
    layout: str = "vertical",
    rows: int = 1,
    cols: int = 1,
    title: str = "",
) -> dict:
    return create_multi_panel_plot(worksheet_name, plot_type, x_col, y_cols or [], panel_labels or [], layout, rows, cols, title)


@mcp.tool(
    description="Add a new curve to an existing graph. Find the graph by name and append a data plot to it."
)
def tool_add_plot_to_graph(
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
    return add_plot_to_graph(graph_name, worksheet_name, x_col, y_col, plot_type, color, symbol_shape, symbol_size, line_width)


# ── Customization Tools ─────────────────────────────────────────────
@mcp.tool(description="Format axis scale type, range, ticks, and grid for a graph.")
def tool_set_axis_format(graph_name: str = "", axis: str = "x", scale_type: str = "", from_: float = None, to: float = None, increment: float = 0, minor_tick_count: int = 1, grid: bool = True, grid_style: str = "solid", grid_color: str = "#E0E0E0", tick_direction: str = "in") -> dict:
    return set_axis_format(graph_name, axis, scale_type, from_, to, increment, minor_tick_count, grid, grid_style, grid_color, tick_direction)


@mcp.tool(description="Set X, Y, and/or Y2 axis labels on a graph with optional font size and bold.")
def tool_set_axis_labels(graph_name: str = "", x_label: str = "", y_label: str = "", y2_label: str = "", font_size: int = 18, bold: bool = False) -> dict:
    return set_axis_labels(graph_name, x_label, y_label, y2_label, font_size, bold)


@mcp.tool(description="Set the main title of a graph with configurable font size, bold, and position.")
def tool_set_graph_title(graph_name: str = "", title: str = "", font_size: int = 22, bold: bool = True, position: str = "top") -> dict:
    return set_graph_title(graph_name, title, font_size, bold, position)


@mcp.tool(description="Modify visual style of an existing plot: color, symbol shape/size, line width/style, fill, transparency, colormap.")
def tool_set_plot_style(graph_name: str = "", plot_index: int = 0, color: str = "", symbol_shape: int = -1, symbol_size: int = -1, line_width: float = -1.0, line_style: str = "", fill_color: str = "", transparency: int = -1, colormap: str = "") -> dict:
    return set_plot_style(graph_name, plot_index, color, symbol_shape, symbol_size, line_width, line_style, fill_color, transparency, colormap)


@mcp.tool(description="Show/hide legend, set position (top-right, top-left, bottom-right, bottom-left, center), and custom labels.")
def tool_set_legend(graph_name: str = "", show: bool = True, position: str = "top-right", font_size: int = 12, custom_labels: list[str] = None) -> dict:
    return set_legend(graph_name, show, position, font_size, custom_labels)


@mcp.tool(description="Add a text annotation at specified coordinates on a graph.")
def tool_add_text_annotation(graph_name: str = "", text: str = "", x: float = 0, y: float = 0, font_size: int = 12, color: str = "#000000") -> dict:
    return add_text_annotation(graph_name, text, x, y, font_size, color)


# ── Analysis Tools ─────────────────────────────────────────────────
@mcp.tool(description="Perform linear regression on data. Returns slope, intercept, R-squared, and optionally generates confidence/prediction bands.")
def tool_fit_linear(worksheet_name: str = "", x_col: int = 0, y_col: int = 1, fix_slope: float = None, fix_intercept: float = None, confidence_band: bool = False, prediction_band: bool = False) -> dict:
    return fit_linear(worksheet_name, x_col, y_col, fix_slope, fix_intercept, confidence_band, prediction_band)


@mcp.tool(description="Perform non-linear curve fitting. Choose from 12 models (Gauss, Lorentz, ExpDecay, Poly, Sine, etc.). Set parameter guesses, fix params, or bounds.")
def tool_fit_nonlinear(worksheet_name: str = "", x_col: int = 0, y_col: int = 1, model: str = "Gauss", param_guesses: dict = None, fix_params: list[str] = None, bounds: dict = None) -> dict:
    return fit_nonlinear(worksheet_name, x_col, y_col, model, param_guesses, fix_params, bounds)


@mcp.tool(description="Perform multi-peak fitting on spectral/chromatography data. Auto-finds peaks and fits them with Gauss or Lorentz models.")
def tool_fit_peak(worksheet_name: str = "", x_col: int = 0, y_col: int = 1, peak_count: int = 1, peak_model: str = "Gauss", auto_find: bool = True) -> dict:
    return fit_peak(worksheet_name, x_col, y_col, peak_count, peak_model, auto_find)


@mcp.tool(description="Compute descriptive statistics (mean, std, min, max, median, sum, count, skew, kurtosis) on a column.")
def tool_compute_statistics(worksheet_name: str = "", column: int = 0, stats: list[str] = None) -> dict:
    return compute_statistics(worksheet_name, column, stats)


# ── Export Tools ────────────────────────────────────────────────────
@mcp.tool(description="Export a graph to an image file (PNG, SVG, EMF, PDF, JPG, TIF, BMP, EPS). Control width, height, DPI, and transparency.")
def tool_export_graph(graph_name: str = "", file_path: str = "", format: str = "png", width: int = 1200, height: int = 0, dpi: int = 300, ratio: int = 100, transparent_bg: bool = False) -> dict:
    return export_graph(graph_name, file_path, format, width, height, dpi, ratio, transparent_bg)


@mcp.tool(description="Save the current Origin project to an .opju file.")
def tool_save_project(file_path: str = "") -> dict:
    return save_project(file_path)


# ── Project Management Tools ──────────────────────────────────────
@mcp.tool(description="List all graph pages in the current Origin project with name, type, and layer count.")
def tool_list_graphs() -> dict:
    return list_graphs()


@mcp.tool(description="List all worksheets in the current Origin project with name, column count, and row count.")
def tool_list_worksheets() -> dict:
    return list_worksheets()


@mcp.tool(description="Get a detailed snapshot of a graph's current state: title, axis labels, scales, and per-plot styles. Use this to inspect a graph before further customization.")
def tool_get_graph_snapshot(graph_name: str = "") -> dict:
    return get_graph_snapshot(graph_name)


def main():
    """Entry point for the MCP server. Uses stdio transport for Claude Desktop integration."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
