# MCP OriginPro — Natural Language-driven Scientific Graphing in Origin 2025b

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.0%2B-green)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](./LICENSE)

An MCP (Model Context Protocol) server that lets AI assistants like OpenCode and Claude Desktop control **Origin 2025b** through natural language. Tell the AI what graph you need and it creates, customizes, analyzes, and exports publication-quality scientific plots.

**25 tools · 52+ plot types · curve fitting (12 models) · statistics · multi-format export**

---

## Overview

MCP OriginPro bridges the gap between conversational AI and OriginPro's powerful COM automation layer. Instead of clicking through menus or memorizing OriginLab's scripting syntax, you describe your graphing task in plain English (or Chinese). The server translates your intent into `originpro` API calls, handles error recovery, and returns meaningful results.

Typical workflow: import CSV data → create a scatter/line/3D plot → customize axes and styles → fit a curve → compute statistics → export to PNG/SVG/PDF. All without touching the Origin GUI.

---

## Features

| Area | Capability |
|------|------------|
| **Plot Types** | 52+ types across 2D, 3D, contour, heatmap, polar, ternary, statistical, and multi-panel layouts |
| **Data Handling** | CSV/TXT/DAT import, programmatic worksheet creation, column-level metadata (long name, units, axis type) |
| **Curve Fitting** | Linear regression with confidence bands, 12 nonlinear models (Gauss, Lorentz, Boltzmann, etc.), multi-peak fitting |
| **Statistics** | Descriptive stats: mean, std, min, max, median, sum, count, skew, kurtosis |
| **Customization** | Axis scales (9 types), ranges, grids; line/symbol styles (7 shapes, 7 line styles); colormaps (12); legend control; text annotations |
| **Export** | 10 formats: PNG, SVG, PDF, EPS, EMF, JPG, TIF, BMP — configurable DPI and transparency |
| **Error Handling** | 4 structured error types with actionable hints for self-correction |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Windows 10 / 11** | OriginPro runs on Windows only |
| **Origin 2025b** | Must be installed with COM automation enabled |
| **Python 3.10+** | Required by `mcp` and `originpro` packages |
| **uv** (recommended) | Fast Python package manager; also works with pip |

> **Critical:** Enable COM automation. In Origin, go to **Tools → System Variables**, find `opj_allow_automation`, set it to `1`, and restart Origin.

---

## Installation

```powershell
# Clone and enter the project
git clone <repo-url> mcp-origin-pro
cd mcp-origin-pro

# Install with uv (recommended)
uv pip install -e .

# Verify
uv run mcp-origin-pro --help
```

### Environment Verification

Run these commands to verify your setup is complete:

```powershell
# 1. Verify Python version (must be 3.10+)
python --version

# 2. Verify uv is installed
uv --version

# 3. Verify originpro package is importable
python -c "import originpro; print('originpro OK')"

# 4. Verify MCP server can start
uv run python -c "from mcp_origin.server import mcp; print('Server OK:', mcp.name)"
```

If step 3 fails, `originpro` is not on your Python path. This package ships with Origin 2025b — ensure Origin is installed, then add its Python subdirectory to `PYTHONPATH`.

If step 4 fails, run `uv pip install -e ".[dev]"` from the project root to install all dependencies.

---

## Client Configuration

### OpenCode

Add to the `servers_config.json` inside your OpenCode workspace:

```json
{
  "mcpServers": {
    "OriginPro": {
      "command": "uv",
      "args": ["run", "mcp-origin-pro"],
      "env": {
        "ORIGIN_AUTO_CONNECT": "true",
        "ORIGIN_DEFAULT_DPI": "300",
        "ORIGIN_DEFAULT_FORMAT": "png",
        "ORIGIN_EXPORT_DIR": "./exports"
      }
    }
  }
}
```

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "OriginPro": {
      "command": "uv",
      "args": ["run", "--directory", "F:/LearnFILE/MCP", "mcp", "run", "server.py"]
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORIGIN_AUTO_CONNECT` | `true` | Auto-connect to Origin on first tool call |
| `ORIGIN_DEFAULT_DPI` | `300` | Default export resolution |
| `ORIGIN_DEFAULT_FORMAT` | `png` | Default export image format |
| `ORIGIN_EXPORT_DIR` | `./exports` | Where exported images are saved |
| `ORIGIN_DEBUG` | `false` | Enable verbose debug logging |

---

## Connectivity Diagnostics

The `ping` tool returns a differentiated `origin_status` field that tells you exactly what's wrong:

| `origin_status` | Meaning | Action |
|---|---|---|
| `connected` | Origin is running ✅ | Proceed with any tool |
| `origin_not_running` | originpro installed, but Origin COM unavailable | Launch Origin 2025b → check `opj_allow_automation=1` → restart Origin |
| `originpro_not_installed` | originpro package missing entirely | Install Origin 2025b with Python support, or add Origin's Python directory to `sys.path` |

### Common Setup Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ping` returns `originpro_not_installed` | `originpro` package not on `sys.path` | Ensure Origin 2025b is installed. The `originpro` package ships with Origin; add its Python directory to `PYTHONPATH` or install via Origin's internal Python |
| `uv` not found in PATH | `uv` package manager not installed | Install uv: `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| `import mcp_origin` fails | Package not installed in editable mode | Run `uv pip install -e .` or `pip install -e .` from project root |
| `mcp dev server.py` fails | Dependencies missing | Run `uv pip install -e ".[dev]"` to install all deps including test tools |
| COM error at runtime even after `ping` passes | Origin session timed out or was closed | Call `ping` again; if still `connected`, restart the MCP server |

---

## Tool Reference

### Meta

| Tool | Description |
|------|-------------|
| `ping` | Check Origin COM connectivity; returns differentiated status ("connected" / "origin_not_running" / "originpro_not_installed") and available plot type count |

### Data Management (4)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `create_worksheet` | Create a new worksheet | `name` |
| `set_column_data` | Fill a column with numeric data | `worksheet_name`, `column`, `data`, `long_name`, `units`, `axis` (X/Y/Z/Error/Label) |
| `import_csv` | Import CSV/TXT/DAT into a worksheet | `file_path`, `worksheet_name`, `start_row`, `end_row` |
| `get_column_info` | Retrieve column metadata (name, units, axis type) | `worksheet_name` |

### Plotting (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `create_plot` | Create any of 52+ plot types | `plot_type`, `worksheet_name`, `x_col`, `y_col`, `y_cols`, `z_col`, `error_col`, `title`, `x_label`, `y_label`, `color`, `colors`, `colormap`, `symbol_shape`, `symbol_size`, `line_width`, `line_style`, `fill_color`, `transparency`, `scale_x`, `scale_y`, `template`, `group_by_col` |
| `create_multi_curve_plot` | Multi-curve plot sharing one X axis | `plot_type`, `worksheet_name`, `x_col`, `y_cols`, `curve_labels`, `colors`, `line_width`, `symbol_size` |
| `create_grouped_plot` | Grouped column/bar by a category column | `plot_type`, `worksheet_name`, `x_col`, `y_col`, `group_col` |
| `create_multi_panel_plot` | Subplot grid layout | `worksheet_name`, `plot_type`, `x_col`, `y_cols`, `panel_labels`, `layout`, `rows`, `cols` |
| `add_plot_to_graph` | Append a curve to an existing graph | `graph_name`, `worksheet_name`, `x_col`, `y_col`, `plot_type`, `color` |

### Customization (6)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `set_axis_format` | Set axis scale, range, ticks, grid | `graph_name`, `axis` (x/y), `scale_type`, `from_`, `to`, `increment`, `grid`, `grid_style`, `grid_color`, `tick_direction` |
| `set_axis_labels` | Set X, Y, and/or Y2 axis labels | `graph_name`, `x_label`, `y_label`, `y2_label`, `font_size`, `bold` |
| `set_graph_title` | Set the main graph title | `graph_name`, `title`, `font_size`, `bold`, `position` |
| `set_plot_style` | Modify symbol, line, fill, colormap | `graph_name`, `plot_index`, `color`, `symbol_shape`, `symbol_size`, `line_width`, `line_style`, `fill_color`, `transparency`, `colormap` |
| `set_legend` | Show/hide and position the legend | `graph_name`, `show`, `position`, `font_size`, `custom_labels` |
| `add_text_annotation` | Add text label at graph coordinates | `graph_name`, `text`, `x`, `y`, `font_size`, `color` |

### Analysis (4)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `fit_linear` | Linear regression with confidence/prediction bands | `worksheet_name`, `x_col`, `y_col`, `fix_slope`, `fix_intercept`, `confidence_band`, `prediction_band` |
| `fit_nonlinear` | Nonlinear curve fitting (12 models) | `worksheet_name`, `x_col`, `y_col`, `model`, `param_guesses`, `fix_params`, `bounds` |
| `fit_peak` | Multi-peak fitting for spectra/chromatograms | `worksheet_name`, `x_col`, `y_col`, `peak_count`, `peak_model` (Gauss/Lorentz), `auto_find` |
| `compute_statistics` | Descriptive statistics on a column | `worksheet_name`, `column`, `stats` (mean/std/min/max/median/sum/count/skew/kurtosis) |

### Export & Project (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `export_graph` | Export a graph to image file | `graph_name`, `file_path`, `format`, `width`, `height`, `dpi`, `transparent_bg`, `ratio` |
| `save_project` | Save the current project as `.opju` | `file_path` |
| `list_graphs` | List all graph pages in the project | — |
| `list_worksheets` | List all worksheets with dimensions | — |
| `get_graph_snapshot` | Inspect a graph's current state (title, axes, curves) | `graph_name` |

---

## Usage Examples

### Example 1: Scatter plot from CSV

**What you say to OpenCode:**
> "Import `C:\data\experiment.csv`, create a scatter plot with column A as X and column B as Y, label the axes 'Time (s)' and 'Concentration (mg/L)', and export it as a 300 DPI PNG."

**What happens behind the scenes:**

```
import_csv(file_path="C:\data\experiment.csv")
 →
create_plot(plot_type="scatter", worksheet_name="experiment", x_col=0, y_col=1,
            title="Experimental Data", x_label="Time (s)", y_label="Concentration (mg/L)")
 →
export_graph(graph_name="Graph1", file_path="experiment.png", dpi=300)
```

### Example 2: Multi-curve comparison with customization

**What you say to OpenCode:**
> "Create a worksheet called 'Comparison', put time values in column 0, then three response curves in columns 1 through 3. Plot them as `line_symbol` with a shared X axis. Name the curves 'Control', 'Treatment A', 'Treatment B'. Use red, blue, and green. Place the legend at top left."

**What happens:**

```
create_worksheet(name="Comparison")
set_column_data(worksheet_name="Comparison", column=0, data=[0,1,2,3,4,5], axis="X")
set_column_data(worksheet_name="Comparison", column=1, data=[1.0, 2.1, 3.0, 4.2, 5.1, 6.0],
                long_name="Control")
set_column_data(worksheet_name="Comparison", column=2, data=[0.8, 1.9, 3.2, 4.5, 5.8, 7.0],
                long_name="Treatment A")
set_column_data(worksheet_name="Comparison", column=3, data=[0.5, 1.2, 2.5, 3.8, 5.2, 6.5],
                long_name="Treatment B")
create_multi_curve_plot(plot_type="line_symbol", worksheet_name="Comparison", x_col=0,
                        y_cols=[1,2,3], curve_labels=["Control","Treatment A","Treatment B"],
                        colors=["red","blue","green"])
set_legend(graph_name="Graph1", position="top-left")
```

### Example 3: 3D surface plot with colormap

**What you say to OpenCode:**
> "I have X, Y, Z columns of temperature distribution data. Create a 3D surface plot using the Rainbow colormap and title it '3D Temperature Field'. Export as SVG."

**What happens:**

```
create_plot(plot_type="3d_surface", worksheet_name="TempData", x_col=0, y_col=1, z_col=2,
            colormap="Rainbow", title="3D Temperature Field")
export_graph(graph_name="Graph1", file_path="temperature.svg", format="svg")
```

### Example 4: Linear fitting with confidence bands

**What you say to OpenCode:**
> "Run linear regression on columns 0 and 1 of the 'Calibration' worksheet with confidence bands enabled. Tell me the R-squared, slope, and intercept."

**What happens:**

```
fit_linear(worksheet_name="Calibration", x_col=0, y_col=1, confidence_band=True)
```

Response includes: `slope`, `intercept`, `r_square`, `adjusted_r_square`, `p_value`, and the confidence band is drawn on the graph.

### Example 5: Multi-peak spectral fitting

**What you say to OpenCode:**
> "Import the Raman spectrum CSV. Plot it as `line`. Auto-find and fit 4 Gaussian peaks."

**What happens:**

```
import_csv(file_path="C:\spectra\raman_spectrum.csv", worksheet_name="Raman")
create_plot(plot_type="line", worksheet_name="Raman", x_col=0, y_col=1,
            title="Raman Spectrum")
fit_peak(worksheet_name="Raman", x_col=0, y_col=1, peak_count=4,
         peak_model="Gauss", auto_find=True)
```

---

## 52+ Plot Types Reference

### 2D Plots (29 types)

| Category | Types |
|----------|-------|
| **Basic** | `line`, `scatter`, `line_symbol`, `column`, `bar`, `area`, `pie` |
| **Stacked** | `stack_column`, `stack_bar`, `stack_area` |
| **Statistical** | `box`, `histogram`, `error_bar`, `x_error_bar` |
| **Advanced** | `bubble`, `color_bubble`, `float_bar`, `high_low_close`, `ohlc_candlestick`, `vector_xyxy`, `vector_xyam` |
| **Specialized** | `polar`, `polar_xr_theta`, `ternary`, `smith_chart`, `windrose`, `dendrogram`, `waterfall_2d`, `double_y` |

### 3D Plots (11 types)

`3d_scatter`, `3d_trajectory`, `3d_surface`, `3d_mesh`, `3d_wireframe`, `3d_bars`, `3d_ribbons`, `3d_walls`, `3d_waterfall`, `3d_vector`, `3d_scatter_error`

### Contour & Heatmap (7 types)

`contour`, `contour_filled`, `contour_line`, `contour_gray`, `heatmap`, `image`, `ternary_contour`

### Multi-Panel Layouts (5 types)

`multi_panel_2v`, `multi_panel_2h`, `multi_panel_4`, `multi_panel_9`, `multi_panel_stack`

### Quick Reference: Scales, Colors, Styles

<details>
<summary><b>Scale types</b> (axis format)</summary>

`linear`, `log10`, `ln`, `log2`, `probability`, `probit`, `reciprocal`, `offset_reciprocal`, `logit`
</details>

<details>
<summary><b>Colormaps</b> (12)</summary>

`Rainbow`, `Fire`, `Maple`, `Cool`, `Heat`, `Temperature`, `Viridis`, `Plasma`, `Jet`, `Ocean`, `Density`, `Candy`
</details>

<details>
<summary><b>Named colors</b> (20)</summary>

`red`, `blue`, `green`, `black`, `white`, `orange`, `purple`, `cyan`, `magenta`, `yellow`, `gray`/`grey`, `darkred`, `darkblue`, `darkgreen`, `navy`, `maroon`, `olive`, `teal`, `silver`

Hex codes (e.g. `#E74C3C`) also accepted.
</details>

<details>
<summary><b>Symbol shapes</b> (7)</summary>

0: square, 1: circle, 2: triangle (up), 3: diamond, 4: cross, 5: plus, 6: triangle (down)

Name aliases like `"diamond"` or `"triangle"` are also accepted.
</details>

<details>
<summary><b>Line styles</b> (7)</summary>

`solid`, `dash`, `dot`, `dash_dot`, `dash_dot_dot`, `short_dash`, `short_dot`
</details>

<details>
<summary><b>Curve fitting models</b> (12)</summary>

`Gauss`, `Lorentz`, `ExpDecay`, `ExpGrowth`, `Poly`, `Line`, `Sine`, `Boltzmann`, `DoseResp`, `Logistic`, `Voigt`, `Allometric1`
</details>

<details>
<summary><b>Export formats</b> (10)</summary>

`png`, `svg`, `emf`, `pdf`, `jpg`/`jpeg`, `tif`/`tiff`, `bmp`, `eps`
</details>

---

## Troubleshooting / FAQ

**Q: "Origin is NOT running" error.**
A: Launch Origin 2025b. Check `Tools → System Variables → opj_allow_automation = 1`. Restart Origin after changing it. Run `ping` to confirm.

**Q: Column indexing — 0-based or 1-based?**
A: All column parameters (`x_col`, `y_col`, `column`, etc.) use **0-based indexing**. Column A = 0, column B = 1, etc.

**Q: Max data per column?**
A: 10,000 rows per column.

**Q: What file path format should I use?**
A: Standard Windows paths. No escaping needed: `C:\Users\You\data.csv`.

**Q: How do I find the name of a worksheet or graph?**
A: Use `list_worksheets` and `list_graphs`. If you leave the name blank, the tool targets the currently active worksheet or graph.

**Q: How do I check what a graph looks like before exporting?**
A: Call `get_graph_snapshot` to get a full status report: title, axis labels, scales, curve count, and per-curve style details.

**Q: Origin threw a COM error. What now?**
A: The server wraps COM errors as `ToolExecutionError` with the original message and a hint. If it persists, restart Origin and try again.

---

## Project Structure

```
mcp-origin-pro/
├── server.py                 # Entry point: `uv run mcp dev server.py`
├── pyproject.toml            # Dependencies and build config
├── .env.example              # Environment variable template
├── src/mcp_origin/
│   ├── server.py             # FastMCP instance + 25 tool registrations
│   ├── utils.py              # Shared helpers
│   ├── core/
│   │   ├── connection.py     # COM connection lifecycle and auto-reconnect
│   │   ├── constants.py      # 52 plot types, colormaps, models, colors, styles
│   │   └── errors.py         # 4 structured error types with hints
│   └── tools/
│       ├── data.py           # create_worksheet, set_column_data, import_csv, get_column_info
│       ├── plot.py           # create_plot, create_multi_curve_plot, create_grouped_plot,
│       │                     #   create_multi_panel_plot, add_plot_to_graph
│       ├── customize.py      # set_axis_format, set_axis_labels, set_graph_title,
│       │                     #   set_plot_style, set_legend, add_text_annotation
│       ├── analysis.py       # fit_linear, fit_nonlinear, fit_peak, compute_statistics
│       ├── export.py         # export_graph, save_project
│       └── project.py        # list_graphs, list_worksheets, get_graph_snapshot
└── tests/                    # pytest-based test suite
```

---

## License

MIT
