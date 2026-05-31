"""MCP project management tools: list_graphs, list_worksheets, get_graph_snapshot.

Three tools that provide read-only introspection of an OriginPro project —
listing graph/worksheet windows and capturing detailed graph state so an
LLM can "see" what a graph looks like before deciding on customisations.

All return standardised ``{"success": bool, ...}`` dicts and follow:
``ensure_origin() → import originpro → operate → format_response``.

The ``get_graph_snapshot`` tool is the key feedback mechanism — it reads
axis labels, scales, plot styles, colours, and symbol attributes for every
plot on every layer, giving the LLM enough context to propose meaningful edits.
"""

from __future__ import annotations

from typing import Any

from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.errors import (
    OriginNotRunningError,
    ToolExecutionError,
    ValidationError,
)
from mcp_origin.utils import format_response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_graph(op: Any, name: str = "") -> Any:
    """Resolve a graph page by name, or return the active graph.

    Args:
        op: The originpro module (already imported).
        name: Graph short-name (e.g. ``"Graph1"``).  Empty = active / first.

    Returns:
        The originpro graph page object.

    Raises:
        ValidationError: No graph matching *name* could be found.
    """
    if name:
        g = op.find_graph(name)
        if g is None:
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
                hint_msg += " No graph windows are open in the project."
            raise ValidationError(
                f"Graph '{name}' not found.",
                details={"graph_name": name, "available": available},
                hint=hint_msg,
            )
        return g

    # No name — find the first graph page.
    for idx in range(len(op.pages)):
        page = op.pages[idx]
        if hasattr(page, "type") and page.type == "g":
            return page
    raise ValidationError(
        "No graph windows are open in the project.",
        hint="Create a graph first using create_plot(), then retry.",
    )


def _safe_get(obj: Any, attr: str, default: Any = "") -> Any:
    """Get an attribute defensively — returns *default* on any failure."""
    try:
        val = getattr(obj, attr, default)
        if val is None:
            return default
        return val
    except Exception:
        return default


# ---------------------------------------------------------------------------
# list_graphs
# ---------------------------------------------------------------------------

def list_graphs() -> dict[str, Any]:
    """List all graph windows in the current OriginPro project.

    Returns:
        Standardised response dict.  On success ``data`` contains
        ``total_graphs`` and ``graphs`` — a list of ``{index, name, type,
        layer_count}`` dicts for every graph page.

    Raises:
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: The originpro API call failed.
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
            tool_name="list_graphs",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    graphs: list[dict[str, Any]] = []

    try:
        for idx in range(len(op.pages)):
            page = op.pages[idx]
            ptype = _safe_get(page, "type", "")
            if ptype != "g":
                continue

            name = _safe_get(page, "name", f"Graph{idx + 1}")
            long_name = _safe_get(page, "long_name", "")

            # Count layers in the graph.
            layer_count = 0
            try:
                layer_count = len(page)
            except Exception:
                # Fallback: try iterating.
                try:
                    layer_count = sum(1 for _ in page)
                except Exception:
                    layer_count = 0

            graphs.append({
                "index": idx,
                "name": name,
                "type": long_name or "graph",
                "layer_count": layer_count,
            })
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to enumerate graph pages: {exc}",
            tool_name="list_graphs",
            details=str(exc),
            hint="Ensure the Origin project has at least one page.",
        ) from exc

    return format_response(
        success=True,
        data={
            "total_graphs": len(graphs),
            "graphs": graphs,
        },
    )


# ---------------------------------------------------------------------------
# list_worksheets
# ---------------------------------------------------------------------------

def list_worksheets() -> dict[str, Any]:
    """List all worksheet windows in the current OriginPro project.

    Returns:
        Standardised response dict.  On success ``data`` contains
        ``total_worksheets`` and ``worksheets`` — a list of ``{index, name,
        column_count, row_count}`` dicts for every worksheet page.

    Raises:
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: The originpro API call failed.
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
            tool_name="list_worksheets",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    worksheets: list[dict[str, Any]] = []

    try:
        for idx in range(len(op.pages)):
            page = op.pages[idx]
            ptype = _safe_get(page, "type", "")
            if ptype != "w":
                continue

            name = _safe_get(page, "name", f"Book{idx + 1}")

            # Column count.
            col_count = 0
            try:
                col_count = len(page.cols)
            except Exception:
                col_count = 0

            # Row count — use the first column's row count as proxy.
            row_count = 0
            try:
                if col_count > 0 and page.cols[0] is not None:
                    # originpro column has a shape-like attribute or __len__.
                    row_count = len(page.cols[0])
            except Exception:
                row_count = 0

            worksheets.append({
                "index": idx,
                "name": name,
                "column_count": col_count,
                "row_count": row_count,
            })
    except Exception as exc:
        raise ToolExecutionError(
            f"Failed to enumerate worksheets: {exc}",
            tool_name="list_worksheets",
            details=str(exc),
            hint="Ensure the Origin project has at least one page.",
        ) from exc

    return format_response(
        success=True,
        data={
            "total_worksheets": len(worksheets),
            "worksheets": worksheets,
        },
    )


# ---------------------------------------------------------------------------
# get_graph_snapshot
# ---------------------------------------------------------------------------

def get_graph_snapshot(
    graph_name: str = "",
) -> dict[str, Any]:
    """Capture a detailed "snapshot" of a graph's visual state.

    This is the key feedback mechanism that lets an LLM "see" what a graph
    currently looks like — axis labels, scales, plot colours, symbol types,
    line widths, etc. — so it can decide on meaningful customisations.

    Every property read is guarded with ``getattr`` / ``try-except`` because
    a graph may be in any state (empty, partially configured, etc.).

    Args:
        graph_name: Short-name of the graph window (e.g. ``"Graph1"``).
            Empty string (default) uses the active / first graph.

    Returns:
        Standardised response dict.  On success ``data`` contains:

        - ``graph_name``: The resolved graph name.
        - ``title``: The graph / page title (if set).
        - ``layers``: A list of layer dicts, each with:
            - ``index``: 0-based layer index.
            - ``x_label``: X-axis label text (string).
            - ``y_label``: Y-axis label text (string).
            - ``x_scale``: X-axis scale info dict (from/to/type if readable).
            - ``y_scale``: Y-axis scale info dict.
            - ``plots``: List of plot dicts, each with:
                - ``index``, ``color``, ``symbol_kind``, ``symbol_size``,
                  ``line_width``, ``plot_type``.

    Raises:
        ValidationError: The requested graph cannot be found.
        OriginNotRunningError: OriginPro is not running.
        ToolExecutionError: The originpro API call failed.
    """
    # ── 1. Connect ─────────────────────────────────────────────────────
    try:
        ensure_origin()
    except OriginNotRunningError:
        raise

    try:
        import originpro as op  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolExecutionError(
            "Failed to import originpro.",
            tool_name="get_graph_snapshot",
            details=str(exc),
            hint="Install OriginPro 2025b and the originpro Python package.",
        ) from exc

    # ── 2. Find graph ──────────────────────────────────────────────────
    try:
        g = _find_graph(op, graph_name)
    except ValidationError:
        raise

    # ── 3. Resolve graph identity ──────────────────────────────────────
    resolved_name: str = graph_name or _safe_get(g, "name", "(active)")
    title: str = _safe_get(g, "long_name", "") or _safe_get(g, "label", "")

    # ── 4. Iterate layers ──────────────────────────────────────────────
    layers: list[dict[str, Any]] = []

    try:
        layer_count = len(g)
    except Exception:
        layer_count = 0

    for li in range(layer_count):
        try:
            layer = g[li]
        except Exception:
            continue

        layer_data: dict[str, Any] = {
            "index": li,
            "x_label": "",
            "y_label": "",
            "x_scale": {},
            "y_scale": {},
            "plots": [],
        }

        # ── Axis labels ────────────────────────────────────────────
        try:
            layer_data["x_label"] = _safe_get(layer, "xlabel", "")
        except Exception:
            pass
        try:
            layer_data["y_label"] = _safe_get(layer, "ylabel", "")
        except Exception:
            pass

        # ── Axis scales ────────────────────────────────────────────
        x_scale: dict[str, Any] = {}
        try:
            x_scale["from"] = _safe_get(layer, "xfrom", None)
        except Exception:
            pass
        try:
            x_scale["to"] = _safe_get(layer, "xto", None)
        except Exception:
            pass
        try:
            x_scale["type"] = _safe_get(layer, "xscale_type", "")
        except Exception:
            pass
        layer_data["x_scale"] = x_scale

        y_scale: dict[str, Any] = {}
        try:
            y_scale["from"] = _safe_get(layer, "yfrom", None)
        except Exception:
            pass
        try:
            y_scale["to"] = _safe_get(layer, "yto", None)
        except Exception:
            pass
        try:
            y_scale["type"] = _safe_get(layer, "yscale_type", "")
        except Exception:
            pass
        layer_data["y_scale"] = y_scale

        # ── Plots ─────────────────────────────────────────────────
        plots: list[dict[str, Any]] = []
        plot_count = 0
        try:
            plot_count = len(layer)
        except Exception:
            pass

        for pi in range(plot_count):
            try:
                plot = layer[pi]
            except Exception:
                continue

            plot_data: dict[str, Any] = {
                "index": pi,
                "color": "",
                "symbol_kind": -1,
                "symbol_size": -1,
                "line_width": -1.0,
                "plot_type": "",
            }

            # Defensive reads — any property may be absent.
            try:
                plot_data["color"] = _safe_get(plot, "color", "")
            except Exception:
                pass

            try:
                sk = _safe_get(plot, "symbol_kind", -1)
                plot_data["symbol_kind"] = sk if sk is not None else -1
            except Exception:
                pass

            try:
                ss = _safe_get(plot, "symbol_size", -1)
                plot_data["symbol_size"] = ss if ss is not None else -1
            except Exception:
                pass

            try:
                lw = _safe_get(plot, "line_width", -1.0)
                plot_data["line_width"] = lw if lw is not None else -1.0
            except Exception:
                pass

            try:
                plot_data["plot_type"] = _safe_get(plot, "type", "")
            except Exception:
                pass

            # Also try to capture line style if available.
            try:
                ls = _safe_get(plot, "line_style", "")
                if ls:
                    plot_data["line_style"] = ls
            except Exception:
                pass

            # Try fill/area colour.
            try:
                fc = _safe_get(plot, "fill_color", "")
                if fc:
                    plot_data["fill_color"] = fc
            except Exception:
                pass

            plots.append(plot_data)

        layer_data["plots"] = plots
        layers.append(layer_data)

    return format_response(
        success=True,
        data={
            "graph_name": resolved_name,
            "title": title,
            "layers": layers,
        },
    )
