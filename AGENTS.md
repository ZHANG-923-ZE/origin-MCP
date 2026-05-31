# AGENTS.md — MCP OriginPro

> **Version:** v0.1.0 (early stage; conventions may evolve)
> **Audience:** AI agents working in this codebase — both tool-user AIs (调用方) and developer AIs (开发方).
> **Language:** This file uses English for technical terms; Chinese annotations appear alongside where Origin's own UI or documentation uses Chinese.

---

## 1. Project Identity (项目概述)

MCP OriginPro (package `mcp-origin-pro`) is an MCP server that bridges conversational AI with **Origin 2025b** COM automation. An AI user describes a graphing task in natural language and the server translates it into `originpro` COM API calls — creating, customizing, analyzing, and exporting publication-quality scientific plots without touching the Origin GUI.

| Property | Value |
|----------|-------|
| Source package | `src/mcp_origin/` (see `pyproject.toml` line 1-6) |
| Python | 3.10+ (see `pyproject.toml` line 5) |
| MCP framework | FastMCP (see `src/mcp_origin/server.py` lines 1-3) |
| COM library | `originpro` (see `pyproject.toml` line 8) |
| Package manager | `uv` (recommended; pip compatible) |
| Platform | **Windows-only** (OriginPro 2025b) |
| License | MIT (see `README.md` line 5) |
| Version | `__version__ = "0.1.0"` in `src/mcp_origin/__init__.py` line 3 |

**Prerequisites:** Origin 2025b installed with COM automation enabled (Tools → System Variables → `opj_allow_automation=1`). See `README.md` lines 35-44 and `src/mcp_origin/core/connection.py` lines 62-71 for the check logic.

**Scope:** 25 tools across 6 domains (data, plot, customize, analysis, export, project), unified behind a single `create_plot(plot_type=...)` entry point supporting 52+ plot types. See `README.md` line 9 and `src/mcp_origin/core/constants.py` lines 27+.

---

## 2. Tool User's Guide (使用者 AI — 工具调用指南)

### 2.1 Tool Categories

| Category | Tools | Primary Use Case |
|----------|-------|------------------|
| **System** (1) | `ping` | Pre-flight connectivity check (MUST call first) |
| **Data** (4) | `create_worksheet`, `set_column_data`, `import_csv`, `get_column_info` | Prepare data containers and populate columns |
| **Plot** (5) | `create_plot`, `create_multi_curve_plot`, `create_grouped_plot`, `create_multi_panel_plot`, `add_plot_to_graph` | Generate 52+ chart types from data |
| **Customize** (6) | `set_axis_format`, `set_axis_labels`, `set_graph_title`, `set_plot_style`, `set_legend`, `add_text_annotation` | Polish axes, styles, labels, annotations |
| **Analysis** (4) | `fit_linear`, `fit_nonlinear`, `fit_peak`, `compute_statistics` | Curve fitting (12 models) and descriptive stats |
| **Export** (2) | `export_graph`, `save_project` | Render to file (8 formats) or save .opju |
| **Project** (3) | `list_graphs`, `list_worksheets`, `get_graph_snapshot` | Inspect current Origin session state |

*Tool count and domain breakdown verified against `src/mcp_origin/server.py` lines 22-280+ and `README.md` line 9.*

### 2.2 Typical Workflow

```
ping → import_csv / create_worksheet + set_column_data
     → create_plot (or specialized variant)
     → set_axis_format / set_axis_labels / set_graph_title
     → fit_linear or fit_nonlinear (optional)
     → export_graph
```

### 2.3 Key Tool Highlights

**`ping`** — Always call first. Returns `{"success": bool, "origin_status": "connected"|"origin_not_running"|"originpro_not_installed"}`. If not connected, the hint field tells you exactly what to fix — whether originpro is missing or Origin needs to be launched. See `src/mcp_origin/server.py` lines 23-67.

**`create_plot`** — Unified entry for 52+ plot types. Pass `plot_type` as a string from these categories (see `src/mcp_origin/tools/plot.py` lines 9-21):

- **2D Basic:** line, scatter, line_symbol, column, bar, area, pie
- **2D Stacked:** stack_column, stack_bar, stack_area
- **2D Statistical:** box, histogram, error_bar, x_error_bar
- **2D Advanced:** bubble, color_bubble, float_bar, high_low_close, ohlc_candlestick, vector_xyxy, vector_xyam
- **2D Specialized:** polar, polar_xr_theta, ternary, smith_chart, windrose, dendrogram, waterfall_2d, double_y
- **3D:** 3d_scatter, 3d_trajectory, 3d_surface, 3d_mesh, 3d_wireframe, 3d_bars, 3d_ribbons, 3d_walls, 3d_waterfall, 3d_vector, 3d_scatter_error
- **Contour/Heatmap:** contour, contour_filled, contour_line, contour_gray, heatmap, image, ternary_contour
- **Multi-Panel:** multi_panel_2v, multi_panel_2h, multi_panel_4, multi_panel_9, multi_panel_stack

All parameters except `plot_type` have defaults; the LLM only needs to specify the type and data source. See `src/mcp_origin/server.py` lines 101-126.

**`import_csv` + `create_worksheet` + `set_column_data`** — Data preparation chain. `import_csv` accepts `.csv`, `.txt`, `.dat` (see `src/mcp_origin/tools/data.py` line 57). `set_column_data` supports axis designations X/Y/Z/Error/Label/Disregard (see `src/mcp_origin/tools/data.py` line 31).

**`export_graph`** — Output formats: PNG, SVG, PDF, EPS, EMF, JPG, TIF, BMP. Configurable DPI (default 300) and transparency. See `src/mcp_origin/tools/export.py`.

### 2.4 Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "Origin not running" | Origin app not launched or COM disabled | Prompt user to launch Origin 2025b; check `opj_allow_automation=1` |
| "No active worksheet" | Called a tool without a data container | Call `create_worksheet` first |
| "Column index out of range" | Column number exceeds worksheet columns | Call `get_column_info` to inspect column layout |
| Wrong worksheet modified | `worksheet_name` omitted (defaults to active) | Always pass explicit `worksheet_name` when multiple sheets exist |
| "object of type 'int' has no len()" | `wks.cols` returns int instead of sequence in some originpro versions | Handled internally by `data.py` — retry the operation (the code wraps `len()` in a try/except) |
| Axis range doesn't cover all data | Setting `axis.scale = 0` (linear) in COM resets axis ranges to template defaults | Fixed in `_set_axis_properties()` — rescale is called first, and the default linear scale is no longer written to COM. If calling originpro directly, always call `gl.rescale()` after `add_plot()` and before `set_axis_format()`. |

*Error hint strings verified against `src/mcp_origin/core/errors.py` lines 64-67, `src/mcp_origin/tools/data.py` lines 80-83.*

---

## 3. Prompt Engineering Guide (Prompt 工程指南)

### 3.1 Good Prompt Template

```
"Import [file.csv] into Origin, create a [plot_type] plot
 with X=[col], Y=[col], title='[title]',
 export as [format] to [path]."
```

Example: *"Import data.csv into Origin, create a scatter plot with X=col(A), Y=col(B), title='Voltage vs Current', export as PNG to ./output/plot.png."*

### 3.2 Anti-Patterns (❌ AI Slop)

1. **Calling tools without `ping` first.** Origin might be offline. Always `ping` → check `success` → proceed.
2. **Not specifying `worksheet_name`.** If omitted, the tool picks the active worksheet, which may not be the one you intended. Risk of overwriting the wrong data.
3. **Not checking `"success": true` in the response.** Every tool returns `format_response()` output (see `src/mcp_origin/utils.py` line 92+). A `false` success flag means the operation failed; the `error` and `hint` fields tell you why and how to fix it.
4. **Passing Chinese characters to English-only parameters.** Parameter names, plot type strings, and color names are English. Only `title`, `x_label`, `y_label`, and text annotations accept Chinese.
5. **Skipping `get_column_info` before using column indices.** Worksheet layouts change. Always check column metadata before referencing `column=3` or `x_col=0`.
6. **Assuming tool succeeded without checking response.** Procedural: after every tool call, read the returned `dict`. If `success` is `false`, read `hint` and retry with corrected parameters.
7. **Forgetting `gl.rescale()` when using originpro directly.** The `create_plot` tool handles rescaling automatically (see §6.4), but if you write raw originpro scripts, you MUST call ``gl.rescale()`` after ``add_plot()`` and before any ``axis.scale`` assignment. Skipping this produces plots whose axes don't cover the data.

### 3.3 Pre-Call Checklist

Before invoking any tool, confirm:

- [ ] `ping` returned `success: true` (within current session)
- [ ] Target worksheet exists (or `create_worksheet` was called)
- [ ] Column indices verified via `get_column_info`
- [ ] All string parameters use correct language (English for codes, any for labels)
- [ ] File paths are valid Windows paths (use forward slashes or raw strings)
- [ ] Plan to check the tool's response `success` field before the next call

---

## 4. Architecture Conventions (架构约定)

### 4.1 Directory Structure

```
src/mcp_origin/
├── __init__.py          # __version__ = "0.1.0"
├── server.py            # FastMCP instance + @mcp.tool() wrappers
├── utils.py             # Shared helpers: parse_color, safe_path, format_response, validate_column_index
├── core/                # NO MCP dependency — pure Origin COM logic
│   ├── connection.py    # ensure_origin(), is_origin_running(), lazy import sentinel
│   ├── errors.py        # Exception hierarchy: OriginProError → 3 subtypes
│   └── constants.py     # PLOT_TYPE_MAP, COLOR_NAMES, SYMBOL_SHAPES, COLORMAPS, LINE_STYLES, etc.
└── tools/               # Per-domain tool implementations (no @mcp.tool() decoration)
    ├── data.py          # create_worksheet, set_column_data, import_csv, get_column_info
    ├── plot.py          # create_plot (unified engine), specialized variants
    ├── customize.py     # set_axis_format, set_axis_labels, set_graph_title, set_plot_style, set_legend, add_text_annotation
    ├── analysis.py      # fit_linear, fit_nonlinear, fit_peak, compute_statistics
    ├── export.py        # export_graph, save_project
    └── project.py       # list_graphs, list_worksheets, get_graph_snapshot
```

*Verified against `src/mcp_origin/` tree listing.*

### 4.2 Layering Principle

```
server.py (FastMCP wrappers)  ←  depends on tools and core
    │
tools/*.py (pure functions)   ←  depends on core and utils
    │
core/ (no MCP imports)        ←  depends on nothing internal
    │
utils.py (shared helpers)     ←  depends on core.errors and core.constants
```

**Dependency rule:** `server → tools → core`, NEVER reverse. The `core/` package imports zero MCP modules. The `tools/` package imports from `core/` and `utils.py` but never from `server.py`. Verified: `src/mcp_origin/tools/data.py` imports `from mcp_origin.core.connection import ensure_origin` (line 14) but never imports `mcp_origin.server`.

### 4.3 Tool Architecture Pattern

Every tool in `tools/*.py` follows this pattern (see `src/mcp_origin/tools/data.py` lines 1-7):

```
ensure_origin() → import originpro → validate inputs → operate (COM calls) → format_response()
```

- `ensure_origin()` raises `OriginNotRunningError` if the COM connection is dead.
- Validation raises `ValidationError(message, hint=..., details=...)` with LLM-actionable hints.
- All return values go through `format_response()` producing `{"success": bool, "error"?: str, "hint"?: str, ...}`.

### 4.4 Exception Hierarchy

Defined in `src/mcp_origin/core/errors.py` lines 12-120+:

```
OriginProError(message, hint, details, tool_name)
├── OriginNotRunningError  — COM unavailable (lines 51-69)
├── ToolExecutionError     — originpro API call failed at runtime (lines 72-95)
└── ValidationError        — invalid user/LLM input (lines 98+)
```

All exceptions expose `to_dict()` (line 36) for JSON serialization. The `hint` field is explicitly designed for LLM self-correction (see `src/mcp_origin/core/errors.py` line 19).

### 4.5 Lazy COM Connection Sentinel

In `src/mcp_origin/core/connection.py` lines 20-24:

```python
_originpro: ModuleType | bool | None = None
# None   = never tried
# False  = tried but failed (Origin not available)
# module = successfully imported
```

`is_origin_running()` (line 45) imports `originpro` at most once per process lifetime. `ensure_origin()` (line 74) is the canonical gate; every tool calls it at the top.

---

## 5. Code Style (代码风格)

All claims verified against actual source files.

### 5.1 File-Level Conventions

- **`from __future__ import annotations`** in EVERY `.py` file. Verified across all 11 source files: `__init__.py`, `server.py`, `utils.py`, `core/__init__.py`, `core/connection.py`, `core/errors.py`, `core/constants.py`, `tools/__init__.py`, `tools/data.py`, `tools/plot.py`, `tools/customize.py`, `tools/analysis.py`, `tools/export.py`, `tools/project.py`.
- **Module docstring format:** `"""One-line summary.\n\nDetailed description."""` (see `src/mcp_origin/tools/data.py` lines 1-7, `src/mcp_origin/tools/plot.py` lines 1-22).

### 5.2 Constants and Data Structures

- **Valid-value sets use `frozenset`.** Examples: `_VALID_AXES` (`tools/data.py` line 31), `_CSV_EXTENSIONS` (`tools/data.py` line 57), `_ERROR_SUPPORTED_TYPES` (`tools/plot.py` line 47).
- **Case-insensitive lookups:** `PLOT_TYPE_MAP` keys are lowercase; `get_plot_info()` normalizes with `.lower()` (`core/constants.py` lines 23-24, and the `get_plot_info` function).
- **Naming:** `_UPPER_CASE` for module-level constants (`_VALID_AXES`, `_SCALE_CODES`, `_DIM_DEFAULT_COLORS`), `snake_case` for functions, `tool_*` prefix for FastMCP wrappers in `server.py`.
- **Bilingual descriptions:** Chinese + English in `PLOT_TYPE_MAP` descriptions (e.g., `"折线图 (Line Plot)"` in `core/constants.py` line 32), tool descriptions in `server.py` (English only for MCP compatibility).

### 5.3 Import Order

Strict ordering observed across all modules (verified in `tools/data.py` lines 9-24, `tools/plot.py` lines 24-40):

```
from __future__ import annotations  # always first

# stdlib imports (alphabetical)
import logging
import os
import re

# typing imports
from typing import Any, TYPE_CHECKING

# project internal imports
from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.errors import ValidationError
from mcp_origin.utils import format_response, parse_color
```

### 5.4 Validation Style

Every validation raises `ValidationError` with three arguments (see `src/mcp_origin/utils.py` lines 44-49, `src/mcp_origin/tools/data.py` lines 80-83):

```python
raise ValidationError(
    message,                    # human-readable error summary
    hint="LLM-actionable suggestion",  # what the AI should try next
    details={"param": value},   # machine-readable context
)
```

The `hint` field is the key design element — it enables the calling AI to self-correct without human intervention.

---

## 6. Workflow Rules (工作流与决策规则)

### 6.1 New Tool Development Process

When adding a new MCP tool:

1. **Classify** the domain: data / plot / customize / analysis / export / project. Place the core logic in the matching `tools/{domain}.py`.
2. **Implement** the core function following the standard pattern: `ensure_origin() → import originpro → validate → operate → format_response()`. See Section 4.3.
3. **Register** a `@mcp.tool()` wrapper in `server.py` with a descriptive `description` string. The wrapper delegates to the core function. Follow `tool_*` naming convention (see `server.py` lines 50-51, 54-57, etc.).
4. **Update** `README.md` tool count if the tool changes the total.
5. **Add tests** in `tests/test_{module}.py` following the patterns described in Section 7.

### 6.2 Exception Decision Tree

- **Origin not running / COM dead?** → `OriginNotRunningError` (already handled by `ensure_origin()`, no extra code needed).
- **Invalid parameter (wrong type, out of range, unsupported value)?** → `ValidationError` with `hint` and `details`.
- **originpro API returned an error?** → `ToolExecutionError` wrapping the underlying COM exception.
- **Need a new error category?** → Subclass `OriginProError` only if the error has a distinct, reusable failure mode. Don't create exception types for one-off validation failures; use `ValidationError` with descriptive `hint` instead.

### 6.3 Parameter Design

- **All parameters have defaults** — the LLM only specifies core args. See `server.py` line 101-125: `tool_create_plot` has 23 parameters; only `plot_type` is required; all others default to sensible values.
- **Unified tool vs specialized tool:** Use the unified `create_plot` for common chart types. Create a specialized tool (`create_multi_curve_plot`, `create_grouped_plot`, `create_multi_panel_plot`) when the workflow requires fundamentally different parameter semantics (multiple Y columns, grouping logic, subplot layouts). Don't add complexity to the unified tool to handle edge cases that cleanly separate.

### 6.4 Axis Rescale Rule (CRITICAL)

**Always call `gl.rescale()` AFTER adding data and BEFORE any axis scale changes.**

The correct order in any plotting function is:

```
add_plot() → style → gl.rescale() → [optional: non-linear scale] → labels
```

**Why this matters:** Writing ``gl.axis("x").scale = 0`` (linear) to Origin's COM layer can **reset the axis range** to the template default (e.g., 0-10), discarding the auto-scaled range. This happens because ``axis.scale`` is a COM property write — it triggers an internal axis rebuild in Origin.

**Concrete bugs this prevents:**
- Plots where data points are outside the visible axis range
- Axis auto-scaling appearing broken for seemingly no reason

**Implementation** (see ``_set_axis_properties()`` in ``src/mcp_origin/tools/plot.py``):
1. Call ``gl.rescale()`` first — fits axes to actual data
2. Only write ``axis.scale`` for **non‑default** types (log10, ln, etc.)
3. Set axis labels last — they're cosmetic and don't affect range

### 6.5 When to Modify `core/constants.py`

Add new entries to `PLOT_TYPE_MAP` when adding a new supported plot type. Add new named colors to `COLOR_NAMES` when Origin introduces new default colors. Do NOT add one-off magic numbers to constants.py; keep them local to the tool module as `_UPPER_CASE` module-level constants.

---

## 7. Testing Strategy (测试策略)

### 7.1 Current State

Tests are minimal: `conftest.py` with `import pytest` and basic fixtures. See `tests/` directory listing (2 files: `__init__.py`, `conftest.py`).

### 7.2 Test Pattern

Because `originpro` requires a running Origin COM session (Windows-only), unit tests **mock the originpro module** and test pure Python logic in `utils.py` and `tools/*.py`.

```python
# Pattern: mock originpro → test pure function logic
def test_parse_color_hex():
    from mcp_origin.utils import parse_color
    assert parse_color("#FF0000") == "#ff0000"
```

### 7.3 Module Organization

`tests/test_{module_name}.py` per source module. For example:
- `tests/test_utils.py` — `parse_color`, `safe_path`, `format_response`, `validate_column_index`
- `tests/test_data.py` — `_find_worksheet` logic, validation branches
- `tests/test_plot.py` — `get_plot_info` lookups, color resolution
- `tests/test_errors.py` — `to_dict()` serialization, hint propagation

### 7.4 Priority Order

1. **`utils.py` pure functions first** — `parse_color`, `safe_path`, `validate_column_index`, `format_response`. Zero COM dependency, fully testable.
2. **`tools/*.py` core logic** — mock `ensure_origin()` and `originpro`, test validation branches and response formatting.
3. **COM integration tests** — manual, require a running Origin instance. Not part of CI.

### 7.5 Running Tests

```bash
uv run pytest           # Run all tests
uv run pytest tests/    # Equivalent
```

Test dependencies are in `pyproject.toml` lines 12-16 (`pytest`, `pytest-asyncio`, `pytest-mock`).

---

## 8. Commit & Release (提交与发布规范)

### 8.1 Commit Format

```
type(scope): description
```

| Type | Use |
|------|-----|
| `feat` | New tool or feature |
| `fix` | Bug fix |
| `refactor` | Code restructuring, no behavior change |
| `docs` | Documentation only (README, AGENTS.md, docstrings) |
| `test` | Test additions or fixes |
| `chore` | Build, deps, config |

| Scope | Covers |
|-------|--------|
| `core` | `core/connection.py`, `core/errors.py`, `core/constants.py` |
| `tools` | Any file under `tools/` |
| `server` | `server.py` (tool registration, FastMCP config) |
| `docs` | README.md, AGENTS.md, inline docs |

Examples:
```
feat(tools): add rose plot support to create_plot
fix(core): handle COM timeout in ensure_origin
refactor(utils): extract hex validation from parse_color
docs: add AGENTS.md with AI conventions
test: add parse_color edge case tests
chore: bump mcp dependency to 1.2.0
```

### 8.2 Version Tracking

Update `__version__` in `src/mcp_origin/__init__.py` line 3. The version string is the single source of truth; `pyproject.toml` line 3 should match.

**Pre-Release Checklist**

```bash
uv run pytest            # All tests pass
uv run pyright src/      # Zero type errors
```

No separate build step required — the package uses `hatchling` (see `pyproject.toml` lines 22-23) and is installed in editable mode during development.

---

## 9. Troubleshooting (排障指南)

### 9.1 Connectivity Diagnostics

The `ping` tool returns a differentiated `origin_status` field.  Always check it before calling any other tool.

| origin_status | Meaning | Action |
|---|---|---|
| `connected` | Everything works ✅ | Proceed with any tool |
| `origin_not_running` | originpro installed but Origin COM unavailable | Launch Origin 2025b → check `opj_allow_automation=1` → restart Origin |
| `originpro_not_installed` | originpro package missing entirely | Install Origin 2025b with Python support, or add Origin's Python dir to sys.path |

### 9.2 Common Setup Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ping` returns `originpro_not_installed` | `originpro` package not on `sys.path` | Ensure Origin 2025b is installed. The `originpro` package ships with Origin; add its Python directory to `PYTHONPATH` or install via Origin's internal Python |
| `uv` not found in PATH | `uv` package manager not installed | Install uv: `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| `import mcp_origin` fails | Package not installed in editable mode | Run `uv pip install -e .` or `pip install -e .` from project root |
| `mcp dev server.py` fails | Dependencies missing | Run `uv pip install -e ".[dev]"` to install all deps including test tools |
| COM error at runtime even after `ping` passes | Origin session timed out or was closed | Call `ping` again; if still `connected`, restart the MCP server |
| ``object of type 'int' has no len()`` on any tool | ``wks.cols`` returns an int (column count) instead of a sequence in some originpro versions | The fix is in ``data.py`` (lines 165-170, 417-422): use try/except ``len()`` and fall back to the int directly |
| Axis ranges don't cover all plotted data | ``axis.scale = 0`` (linear) written to COM resets the axis range to template defaults | The fix is in ``_set_axis_properties()`` in ``plot.py``: rescale *before* any scale write, and skip writing the default ``linear`` scale. For direct originpro scripts: always call ``gl.rescale()`` after ``add_plot()`` |

### 9.3 Environment Verification Commands

```bash
# Verify Python + originpro
python -c "import originpro; print('originpro OK')"

# Verify uv
uv --version

# Install project in editable mode
uv pip install -e ".[dev]"

# Verify server starts
uv run python -c "from mcp_origin.server import mcp; print('Server OK:', mcp.name)"
```

---

## 10. Quick Reference (环境速查)

### 10.1 Common Commands

| Action | Command |
|--------|---------|
| Start dev MCP server | `uv run mcp dev server.py` |
| Install to Claude Desktop | `uv run mcp install server.py` |
| Run all tests | `uv run pytest` |
| Run specific test file | `uv run pytest tests/test_utils.py` |
| Type check | `uv run pyright src/` |
| Format / lint | *(not yet configured; add `ruff` or `black` as needed)* |

### 10.2 Environment Variables

From `.env.example`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ORIGIN_AUTO_CONNECT` | `true` | Auto-verify Origin connection on first call |
| `ORIGIN_DEFAULT_DPI` | `300` | Default export resolution |
| `ORIGIN_DEFAULT_FORMAT` | `png` | Default export format |
| `ORIGIN_EXPORT_DIR` | `./exports` | Default export output directory |
| `ORIGIN_DEBUG` | `false` | Enable verbose logging |

### 10.3 Key File Map

| What | Where |
|------|-------|
| MCP server entry | `server.py` (root) → delegates to `src/mcp_origin/server.py` |
| Tool implementations | `src/mcp_origin/tools/{data,plot,customize,analysis,export,project}.py` |
| Plot type registry | `src/mcp_origin/core/constants.py` → `PLOT_TYPE_MAP` |
| Error classes | `src/mcp_origin/core/errors.py` |
| COM connection | `src/mcp_origin/core/connection.py` |
| Shared utilities | `src/mcp_origin/utils.py` |
| Version | `src/mcp_origin/__init__.py` → `__version__` |
| Dependencies | `pyproject.toml` |
| Notepads (learnings) | `.sisyphus/notepads/` |
| Plans (read-only) | `.sisyphus/plans/` |

---

*End of AGENTS.md. If you find a pattern not documented here, check the codebase first; if it's real and recurring, add it.*
