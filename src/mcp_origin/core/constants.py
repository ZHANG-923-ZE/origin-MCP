"""Plot type mapping table, symbol/style constants, and lookup helpers.

The centrepiece is ``PLOT_TYPE_MAP`` — a case-insensitive dictionary that maps
human-readable plot type strings to Origin template names, plot type IDs,
descriptions, and dimensionality categories.
"""

from __future__ import annotations

from typing import Any

# ============================================================================
# PLOT TYPE MAP — 48+ Origin plot types
# ============================================================================
# Each entry: {"template", "id", "description", "dim"}
#
#   template     : Origin graph template name (without .otp extension).
#   id           : Origin numeric plot type ID (can be None for multi-panel
#                  / special templates that don't have a single ID).
#   description  : Human-readable description (Chinese + English).
#   dim          : Category: "2d", "3d", "contour", "panel", or "special".
#
# Keys are guaranteed lowercase; `get_plot_info()` does case-insensitive
# lookup so callers never need to worry about casing.
# ============================================================================

PLOT_TYPE_MAP: dict[str, dict[str, Any]] = {
    # ── 2D BASIC ──────────────────────────────────────────────────────
    "line": {
        "template": "line",
        "id": 200,
        "description": "折线图 (Line Plot)",
        "dim": "2d",
    },
    "scatter": {
        "template": "scatter",
        "id": 201,
        "description": "散点图 (Scatter Plot)",
        "dim": "2d",
    },
    "line_symbol": {
        "template": "linesymb",
        "id": 202,
        "description": "线+符号图 (Line + Symbol)",
        "dim": "2d",
    },
    "column": {
        "template": "column",
        "id": 203,
        "description": "柱状图 (Column Plot)",
        "dim": "2d",
    },
    "bar": {
        "template": "bar",
        "id": 215,
        "description": "条形图 (Bar Chart)",
        "dim": "2d",
    },
    "area": {
        "template": "area",
        "id": 204,
        "description": "面积图 (Area Plot)",
        "dim": "2d",
    },
    "pie": {
        "template": "pie",
        "id": 225,
        "description": "饼图 (Pie Chart)",
        "dim": "2d",
    },

    # ── 2D STACKED ────────────────────────────────────────────────────
    "stack_column": {
        "template": "column",
        "id": 213,
        "description": "堆叠柱状图 (Stacked Column)",
        "dim": "2d",
    },
    "stack_bar": {
        "template": "bar",
        "id": 216,
        "description": "堆叠条形图 (Stacked Bar)",
        "dim": "2d",
    },
    "stack_area": {
        "template": "stackarea",
        "id": 214,
        "description": "堆叠面积图 (Stacked Area)",
        "dim": "2d",
    },

    # ── 2D STATISTICAL ────────────────────────────────────────────────
    "box": {
        "template": "box",
        "id": 206,
        "description": "箱线图 (Box Chart)",
        "dim": "2d",
    },
    "histogram": {
        "template": "hist",
        "id": 219,
        "description": "直方图 (Histogram)",
        "dim": "2d",
    },
    "error_bar": {
        "template": "Errbar",
        "id": 231,
        "description": "Y误差棒图 (Y Error Bar)",
        "dim": "2d",
    },
    "x_error_bar": {
        "template": "Errbar",
        "id": 233,
        "description": "X误差棒图 (X Error Bar)",
        "dim": "2d",
    },

    # ── 2D ADVANCED ───────────────────────────────────────────────────
    "bubble": {
        "template": "scatter",
        "id": 193,
        "description": "气泡图-索引大小 (Bubble)",
        "dim": "2d",
    },
    "color_bubble": {
        "template": "scatter",
        "id": 194,
        "description": "气泡图-颜色映射 (Color-mapped Bubble)",
        "dim": "2d",
    },
    "float_bar": {
        "template": "floatbar",
        "id": 207,
        "description": "浮动条形图 (Floating Bar)",
        "dim": "2d",
    },
    "high_low_close": {
        "template": "hclose",
        "id": 205,
        "description": "高低收盘图 (High-Low-Close)",
        "dim": "2d",
    },
    "ohlc_candlestick": {
        "template": "Candlestick",
        "id": 221,
        "description": "K线图/蜡烛图 (OHLC Candlestick)",
        "dim": "2d",
    },
    "vector_xyxy": {
        "template": "vectxyxy",
        "id": 218,
        "description": "向量图 XYXY (Vector XYXY)",
        "dim": "2d",
    },
    "vector_xyam": {
        "template": "vector",
        "id": 208,
        "description": "向量图 XYAM (Vector XYAM)",
        "dim": "2d",
    },

    # ── 2D SPECIALIZED ────────────────────────────────────────────────
    "polar": {
        "template": "polar",
        "id": 192,
        "description": "极坐标图 (Polar Plot)",
        "dim": "2d",
    },
    "polar_xr_theta": {
        "template": "PolarXrYTheta",
        "id": 186,
        "description": "极坐标 X=R Y=θ",
        "dim": "2d",
    },
    "ternary": {
        "template": "Ternary",
        "id": None,
        "description": "三元相图 (Ternary Plot)",
        "dim": "2d",
    },
    "smith_chart": {
        "template": "SmithCht",
        "id": 191,
        "description": "史密斯圆图 (Smith Chart)",
        "dim": "2d",
    },
    "windrose": {
        "template": "windrose",
        "id": 213,
        "description": "风玫瑰图 (Wind Rose)",
        "dim": "2d",
    },
    "dendrogram": {
        "template": "Cluster",
        "id": 108,
        "description": "树状图/聚类图 (Dendrogram)",
        "dim": "2d",
    },
    "waterfall_2d": {
        "template": "waterfall",
        "id": None,
        "description": "2D瀑布图 (2D Waterfall)",
        "dim": "2d",
    },
    "double_y": {
        "template": "DoubleY",
        "id": None,
        "description": "双Y轴图 (Double Y)",
        "dim": "2d",
    },

    # ── 3D ────────────────────────────────────────────────────────────
    "3d_scatter": {
        "template": "gl3DScatter",
        "id": 240,
        "description": "3D散点图 (3D Scatter)",
        "dim": "3d",
    },
    "3d_trajectory": {
        "template": "glTraject",
        "id": 240,
        "description": "3D轨迹图 (3D Trajectory)",
        "dim": "3d",
    },
    "3d_surface": {
        "template": "glcmap",
        "id": 242,
        "description": "3D曲面图-颜色映射 (3D Colormap Surface)",
        "dim": "3d",
    },
    "3d_mesh": {
        "template": "mesh",
        "id": 242,
        "description": "3D网格曲面 (3D Mesh)",
        "dim": "3d",
    },
    "3d_wireframe": {
        "template": "glwirefrm",
        "id": 242,
        "description": "3D线框曲面 (3D Wireframe)",
        "dim": "3d",
    },
    "3d_bars": {
        "template": "bar3d",
        "id": 212,
        "description": "3D柱状图 (3D Bars)",
        "dim": "3d",
    },
    "3d_ribbons": {
        "template": "ribbon",
        "id": 211,
        "description": "3D带条图 (3D Ribbons)",
        "dim": "3d",
    },
    "3d_walls": {
        "template": "walls",
        "id": 210,
        "description": "3D墙壁图 (3D Walls)",
        "dim": "3d",
    },
    "3d_waterfall": {
        "template": "glWater3D",
        "id": 210,
        "description": "3D瀑布图 (3D Waterfall)",
        "dim": "3d",
    },
    "3d_vector": {
        "template": "gl3DVector",
        "id": 183,
        "description": "3D向量图 (3D Vector)",
        "dim": "3d",
    },
    "3d_scatter_error": {
        "template": "gl3DError",
        "id": 184,
        "description": "3D散点+误差棒 (3D Scatter+Error)",
        "dim": "3d",
    },

    # ── CONTOUR / HEATMAP / IMAGE ─────────────────────────────────────
    "contour": {
        "template": "contour",
        "id": 226,
        "description": "等高线图 (Contour)",
        "dim": "contour",
    },
    "contour_filled": {
        "template": "contour",
        "id": 226,
        "description": "填充等高线图 (Filled Contour)",
        "dim": "contour",
    },
    "contour_line": {
        "template": "contline",
        "id": 226,
        "description": "等高线图-仅线 (Contour Lines Only)",
        "dim": "contour",
    },
    "contour_gray": {
        "template": "contgray",
        "id": 226,
        "description": "灰度等高线图 (Grayscale Contour)",
        "dim": "contour",
    },
    "heatmap": {
        "template": "heatmap",
        "id": 105,
        "description": "热力图 (Heatmap)",
        "dim": "contour",
    },
    "image": {
        "template": "image",
        "id": 220,
        "description": "图像图 (Image Plot)",
        "dim": "contour",
    },
    "ternary_contour": {
        "template": "TernaryContour",
        "id": 185,
        "description": "三元等高线 (Ternary Contour)",
        "dim": "contour",
    },

    # ── MULTI-PANEL ──────────────────────────────────────────────────
    "multi_panel_2v": {
        "template": "PAN2VERT",
        "id": None,
        "description": "2行垂直面板 (2-Vertical Panel)",
        "dim": "panel",
    },
    "multi_panel_2h": {
        "template": "PAN2HORIZ",
        "id": None,
        "description": "2列水平面板 (2-Horizontal Panel)",
        "dim": "panel",
    },
    "multi_panel_4": {
        "template": "PAN4",
        "id": None,
        "description": "2×2四面板 (2x2 Panel)",
        "dim": "panel",
    },
    "multi_panel_9": {
        "template": "PAN9",
        "id": None,
        "description": "3×3九面板 (3x3 Panel)",
        "dim": "panel",
    },
    "multi_panel_stack": {
        "template": "Stack",
        "id": None,
        "description": "堆叠多面板 (Stacked Multi-Panel)",
        "dim": "panel",
    },
}

# ============================================================================
# SYMBOL SHAPES (Origin integer codes)
# ============================================================================
SYMBOL_SHAPES: dict[int, str] = {
    0: "square",
    1: "circle",
    2: "up_triangle",
    3: "diamond",
    4: "cross",
    5: "plus",
    6: "down_triangle",
}

# Reverse lookup for convenience: "circle" → 1
_SYMBOL_SHAPE_NAMES: dict[str, int] = {v: k for k, v in SYMBOL_SHAPES.items()}

# ============================================================================
# LINE STYLES (Origin integer codes)
# ============================================================================
LINE_STYLES: dict[str, int] = {
    "solid": 0,
    "dash": 1,
    "dot": 2,
    "dash_dot": 3,
    "dash_dot_dot": 4,
    "short_dash": 5,
    "short_dot": 6,
}

# ============================================================================
# COLORMAPS (Origin built-in palette names)
# ============================================================================
COLORMAPS: list[str] = [
    "Rainbow",
    "Fire",
    "Maple",
    "Cool",
    "Heat",
    "Temperature",
    "Viridis",
    "Plasma",
    "Jet",
    "Ocean",
    "Density",
    "Candy",
]

# ============================================================================
# SCALE TYPES (for axes)
# ============================================================================
SCALE_TYPES: list[str] = [
    "linear",
    "log10",
    "ln",
    "log2",
    "probability",
    "probit",
    "reciprocal",
    "offset_reciprocal",
    "logit",
]

# ============================================================================
# COLOR NAMES → HEX
# ============================================================================
COLOR_NAMES: dict[str, str] = {
    "red": "#FF0000",
    "blue": "#0000FF",
    "green": "#008000",
    "black": "#000000",
    "white": "#FFFFFF",
    "orange": "#FFA500",
    "purple": "#800080",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "yellow": "#FFFF00",
    "gray": "#808080",
    "grey": "#808080",
    "darkred": "#8B0000",
    "darkblue": "#00008B",
    "darkgreen": "#006400",
    "navy": "#000080",
    "maroon": "#800000",
    "olive": "#808000",
    "teal": "#008080",
    "silver": "#C0C0C0",
}

# ============================================================================
# CURVE FITTING MODELS
# ============================================================================
FIT_MODELS: list[str] = [
    "Gauss",
    "Lorentz",
    "ExpDecay",
    "ExpGrowth",
    "Poly",
    "Line",
    "Sine",
    "Boltzmann",
    "DoseResp",
    "Logistic",
    "Voigt",
    "Allometric1",
]

# ============================================================================
# EXPORT FORMATS (MIME extension → Origin export extension)
# ============================================================================
EXPORT_FORMATS: dict[str, str] = {
    "png": "png",
    "svg": "svg",
    "emf": "emf",
    "pdf": "pdf",
    "jpg": "jpg",
    "jpeg": "jpeg",
    "tif": "tif",
    "tiff": "tiff",
    "bmp": "bmp",
    "eps": "eps",
}


# ============================================================================
# LOOKUP HELPERS
# ============================================================================

def get_plot_info(plot_type: str) -> dict[str, Any]:
    """Case-insensitive lookup of plot type metadata.

    Args:
        plot_type: Plot type key (e.g. ``"scatter"``, ``"3D_SURFACE"``).

    Returns:
        Dict with keys ``template``, ``id``, ``description``, ``dim``.

    Raises:
        KeyError: The plot type string is not recognised.
    """
    try:
        return PLOT_TYPE_MAP[plot_type.lower()]
    except KeyError:
        available = ", ".join(sorted(PLOT_TYPE_MAP.keys()))
        raise KeyError(
            f"Unknown plot type '{plot_type}'. Available types: {available}"
        ) from None


def get_symbol_code(shape_name: str) -> int:
    """Return the Origin symbol integer code for a human-readable shape name.

    Accepts common aliases: ``"circle"``, ``"square"``, ``"triangle"``, etc.

    Args:
        shape_name: Symbol shape (case-insensitive).

    Returns:
        Integer code recognised by Origin's ``symbol_kind`` property.

    Raises:
        KeyError: The shape name is not recognised.
    """
    name = shape_name.lower()
    if name in _SYMBOL_SHAPE_NAMES:
        return _SYMBOL_SHAPE_NAMES[name]

    # Accept some common aliases.
    aliases: dict[str, str] = {
        "triangle": "up_triangle",
        "downward_triangle": "down_triangle",
        "tri": "up_triangle",
        "dtri": "down_triangle",
    }
    resolved = aliases.get(name)
    if resolved is not None:
        return _SYMBOL_SHAPE_NAMES[resolved]

    available = sorted(_SYMBOL_SHAPE_NAMES.keys())
    raise KeyError(
        f"Unknown symbol shape '{shape_name}'. Available: {available}"
    )


def list_plot_types(dim: str | None = None) -> list[str]:
    """Return the registered plot type keys, optionally filtered by dimension.

    Args:
        dim: Filter by dimension category (``"2d"``, ``"3d"``, ``"contour"``,
             ``"panel"``, or ``"special"``).  Pass ``None`` to return all.

    Returns:
        Sorted list of plot type keys.
    """
    if dim is None:
        return sorted(PLOT_TYPE_MAP.keys())
    return sorted(
        k for k, v in PLOT_TYPE_MAP.items() if v.get("dim") == dim
    )
