"""Core modules: Origin COM connection, error handling, and plot-type constants."""

from mcp_origin.core.connection import (
    ensure_origin,
    get_origin_app,
    is_origin_running,
    reset_connection,
)
from mcp_origin.core.constants import (
    COLORMAPS,
    COLOR_NAMES,
    EXPORT_FORMATS,
    FIT_MODELS,
    LINE_STYLES,
    PLOT_TYPE_MAP,
    SCALE_TYPES,
    SYMBOL_SHAPES,
    get_plot_info,
    get_symbol_code,
    list_plot_types,
)
from mcp_origin.core.errors import (
    OriginNotRunningError,
    OriginProError,
    ToolExecutionError,
    ValidationError,
)

__all__ = [
    # connection
    "ensure_origin",
    "get_origin_app",
    "is_origin_running",
    "reset_connection",
    # constants
    "COLORMAPS",
    "COLOR_NAMES",
    "EXPORT_FORMATS",
    "FIT_MODELS",
    "LINE_STYLES",
    "PLOT_TYPE_MAP",
    "SCALE_TYPES",
    "SYMBOL_SHAPES",
    "get_plot_info",
    "get_symbol_code",
    "list_plot_types",
    # errors
    "OriginProError",
    "OriginNotRunningError",
    "ToolExecutionError",
    "ValidationError",
]
