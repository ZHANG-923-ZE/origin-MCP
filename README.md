# MCP OriginPro — 自然语言驱动 Origin 2025b 科学绘图

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.0%2B-green)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](./LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)](https://www.originlab.com/)

**MCP OriginPro** 是一个 MCP (Model Context Protocol) 服务器，让 AI 编程助手（OpenCode、Claude Desktop 等）通过自然语言控制 **Origin 2025b**。你只需用中文或英文描述想要的图表，AI 就能自动创建、定制、分析和导出发表级科学图表 —— 全程无需触碰 Origin GUI。

**26 个工具 · 52+ 种图表 · 曲线拟合（12 模型）· 统计分析 · 多格式导出**

---

## 项目概述

在科研工作中，用 Origin 画图通常需要在 GUI 中反复点击菜单、调整参数。MCP OriginPro 将这个过程完全自动化：AI 助手理解你的自然语言指令，翻译成 `originpro` COM API 调用，直接在 Origin 中生成图表。

典型场景：
> "帮我把 data.csv 导入 Origin，用第一列做 X 轴、第二列做 Y 轴画散点图，标题写'电压-电流关系曲线'，坐标轴标注中文，线性拟合后导出 PNG。"

---

## 核心功能

| 类别 | 工具数 | 工具 | 功能 |
|------|--------|------|------|
| **系统** | 1 | `ping` | 连接检测（必须先调用） |
| **数据** | 4 | `create_worksheet` `set_column_data` `import_csv` `get_column_info` | 创建工作表、导入 CSV/TXT/DAT、设置列数据 |
| **绘图** | 5 | `create_plot` `create_multi_curve_plot` `create_grouped_plot` `create_multi_panel_plot` `add_plot_to_graph` | 统一绘图入口，支持 52+ 图表类型 |
| **定制** | 6 | `set_axis_format` `set_axis_labels` `set_graph_title` `set_plot_style` `set_legend` `add_text_annotation` | 坐标轴、标签、标题、样式、图例、文本注释 |
| **分析** | 4 | `fit_linear` `fit_nonlinear` `fit_peak` `compute_statistics` | 线性拟合、非线性拟合（12 模型）、寻峰、描述统计 |
| **导出** | 2 | `export_graph` `save_project` | 导出 PNG/SVG/PDF/EPS/EMF/JPG/TIF/BMP、保存 .opju |
| **项目** | 3 | `list_graphs` `list_worksheets` `get_graph_snapshot` | 查看当前 Origin 会话中的图表和工作表 |

### 支持的绘图类型

**2D 基础**: line, scatter, line_symbol, column, bar, area, pie  
**2D 堆叠**: stack_column, stack_bar, stack_area  
**2D 统计**: box, histogram, error_bar, x_error_bar  
**2D 高级**: bubble, color_bubble, float_bar, high_low_close, ohlc_candlestick, vector_xyxy, vector_xyam  
**2D 专题**: polar, polar_xr_theta, ternary, smith_chart, windrose, dendrogram, waterfall_2d, double_y  
**3D**: 3d_scatter, 3d_trajectory, 3d_surface, 3d_mesh, 3d_wireframe, 3d_bars, 3d_ribbons, 3d_walls, 3d_waterfall, 3d_vector, 3d_scatter_error  
**等高线/热图**: contour, contour_filled, contour_line, contour_gray, heatmap, image, ternary_contour  
**多面板**: multi_panel_2v, multi_panel_2h, multi_panel_4, multi_panel_9, multi_panel_stack

### 曲线拟合与统计

**分析功能**:
- 线性回归（支持固定斜率/截距、置信带、预测带）
- 非线性拟合（Gauss, Lorentz, Boltzmann, ExpDecay, Poly, Sine 等 12 种模型）
- 多峰拟合（自动寻峰 + Gauss/Lorentz 拟合）
- 描述统计（均值、标准差、最小值、最大值、中位数、总和、偏度、峰度）

---

## 前置要求

| 要求 | 说明 |
|------|------|
| **Windows 10 / 11** | Origin 2025b 仅支持 Windows |
| **Origin 2025b** | 必须安装（Origin 2024 部分兼容） |
| **COM 自动化** | 在 Origin 中：**工具 → 系统变量** → 找到 `opj_allow_automation` → 设为 `1` → 重启 Origin |
| **Python 3.10+** | 运行服务器所需 |
| **uv**（推荐）| 快速 Python 包管理工具；也可用 pip |

> **关键步骤**: COM 自动化默认关闭。不启用则所有工具都会报 `origin_not_running`。

验证 COM 是否正常：
```bash
python -c "import originpro; print('originpro OK')"
```

---

## 安装与部署

### 1. 克隆项目
```powershell
git clone https://github.com/ZHANG-923-ZE/origin-MCP.git
cd origin-MCP
```

### 2. 安装依赖
```powershell
uv pip install -e .          # 基础安装
uv pip install -e ".[dev]"   # 含开发工具 (pytest, ruff, pyright)
```

> `originpro` 随 Origin 2025b 安装提供，不在 PyPI 上。确保 Origin 已安装且其 Python 目录在 `sys.path` 中。

### 3. 验证服务器
```powershell
uv run python -c "from mcp_origin.server import mcp; print('Server:', mcp.name)"
# 输出: Server: OriginPro
```

### 4. 配置 OpenCode

编辑 `.opencode/opencode.json`（项目根目录或全局 `~/.config/opencode/opencode.json`）：

```json
{
  "mcpServers": {
    "originpro": {
      "command": "uv",
      "args": ["run", "--directory", "F:/LearnFILE/MCP", "mcp", "dev", "server.py"]
    }
  }
}
```

### 5. 配置 Claude Desktop

编辑 Claude Desktop 配置文件：

```json
{
  "mcpServers": {
    "originpro": {
      "command": "uv",
      "args": ["run", "--directory", "C:/path/to/origin-MCP", "mcp", "run", "server.py"]
    }
  }
}
```

### 6. 启动 Origin 2025b

在使用任何绘图工具前，确保 Origin 2025b 已启动。MCP 服务器通过 COM 协议与 Origin 通信，Origin 必须处于运行状态。

---

## 工作原理

### 整体架构

```
AI 助手 (自然语言)
    │
    ▼
FastMCP Server (server.py)     ← MCP 协议层
    │
    ├── tools/data.py           ← 数据准备
    ├── tools/plot.py           ← 统一绘图引擎 (create_plot)
    ├── tools/customize.py      ← 图表定制
    ├── tools/analysis.py       ← 曲线拟合 & 统计
    ├── tools/export.py         ← 导出 & 保存
    ├── tools/project.py        ← 项目管理
    │
    ├── core/connection.py      ← COM 连接管理 (惰性加载)
    ├── core/errors.py          ← 异常体系 (4 类)
    └── core/constants.py       ← 绘图类型映射 (PLOT_TYPE_MAP)
    │
    ▼
Origin 2025b COM API            ← originpro 包
```

### 分层设计

```
server.py (FastMCP 包装器)  ← 依赖 tools 和 core
    │
tools/*.py (纯函数)          ← 依赖 core 和 utils
    │
core/ (不导入 MCP)            ← 不依赖任何内部模块
```

- **server.py** 负责 MCP 协议层的 `@mcp.tool()` 注册，将 AI 调用转发给 tools 层
- **tools/*.py** 实现具体的业务逻辑，每个函数遵循 `ensure_origin() → validate → operate → format_response()` 模式
- **core/connection.py** 管理 Origin COM 连接，采用惰性加载策略（首次调用时才导入 originpro）
- **core/errors.py** 定义 4 类结构化异常，每类异常都携带 `hint` 字段供 AI 自动修正

### 异常处理

所有错误继承自 `OriginProError`，返回结构化 JSON（`success`, `error`, `hint`, `details`）。AI 可根据 `hint` 字段自动修正参数重试：

| 异常类型 | 触发条件 | hint 示例 |
|----------|----------|-----------|
| `OriginNotRunningError` | COM 不可用 | "请启动 Origin 2025b" |
| `ToolExecutionError` | COM API 调用失败 | 具体 API 错误信息 |
| `ValidationError` | 参数无效 | 有效值列表或修正建议 |

### 统一绘图入口

`create_plot(plot_type="scatter", ...)` 是核心绘图工具。只需传入 `plot_type` 字符串，其余参数均有默认值。支持的绘图类型定义在 `core/constants.py` 的 `PLOT_TYPE_MAP` 中（48+ 条目）。

---

## 项目结构

```
origin-MCP/
├── server.py                  # MCP 服务器入口 (thin wrapper)
├── run_server.py              # 独立运行脚本
├── pyproject.toml             # 项目配置 (hatchling)
├── LICENSE                    # MIT 许可证
├── README.md                  # 本文件
├── AGENTS.md                  # AI 代理开发指南
├── sample.csv                 # 示例数据文件
├── src/mcp_origin/
│   ├── __init__.py            # __version__ = "0.1.0"
│   ├── server.py              # FastMCP 实例 + @mcp.tool() 注册
│   ├── utils.py               # parse_color, safe_path, format_response
│   ├── core/
│   │   ├── connection.py      # Origin COM 连接管理
│   │   ├── errors.py          # 异常层级 (4 类)
│   │   └── constants.py       # PLOT_TYPE_MAP, 颜色/符号/线型常量
│   └── tools/
│       ├── data.py            # 数据准备工具 (4)
│       ├── plot.py            # 绘图工具 (5) — 统一 create_plot 引擎
│       ├── customize.py       # 定制工具 (6)
│       ├── analysis.py        # 分析工具 (4)
│       ├── export.py          # 导出工具 (2)
│       └── project.py         # 项目管理工具 (3)
└── tests/                     # 测试目录
    ├── __init__.py
    └── conftest.py
```

---

## 使用示例

### 典型工作流

```
ping                          → 检查连接
import_csv("data.csv")        → 导入数据
create_plot(                  → 创建图表
  plot_type="scatter",
  x_col=0, y_col=1
)
set_axis_labels(              → 设置坐标轴标签
  x_label="时间 (s)",
  y_label="电压 (V)"
)
set_graph_title(              → 设置标题
  title="电压-时间曲线"
)
fit_linear()                  → 线性拟合
export_graph(                 → 导出图片
  file_path="./output.png"
)
```

### 自然语言示例

对 AI 助手说：

**散点图 + 线性拟合**:
> "导入 data.csv，以 col(A) 为 X、col(B) 为 Y 画散点图，标题'电压-电流特性曲线'，线性拟合并显示 R²，导出为 PNG"

**多曲线对比图**:
> "用多曲线图对比三组实验数据，X 轴用 col(A)，Y 轴用 col(B)/col(C)/col(D)，分别标注为'对照组'、'实验组1'、'实验组2'"

**3D 曲面图**:
> "画 3D 曲面图，X=col(A) Y=col(B) Z=col(C)，用 Jet 色图，标题'温度场分布'"

---

## 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `ping` 返回 `origin_not_running` | Origin 2025b 未启动 | 启动 Origin 2025b |
| `ping` 返回 `originpro_not_installed` | originpro 不在 Python 路径 | 安装 Origin 2025b 或添加其 Python 目录到 `PYTHONPATH` |
| "No active worksheet" | 未创建数据容器 | 先调用 `create_worksheet` |
| "Column index out of range" | 列号超出范围 | 调用 `get_column_info` 检查列布局 |
| 修改了错误的工作表 | 未指定 `worksheet_name` | 总是显式传入 `worksheet_name` |
| 数据点超出坐标轴范围 | `axis.scale` 操作问题 | `create_plot` 已自动处理；直接调用 originpro 时注意 `gl.rescale()` |
| 中文参数报错 | 参数名必须用英文 | 只有 `title`、`x_label`、`y_label` 和文本注释支持中文 |
| 调用工具前未 `ping` | 不知道 Origin 是否在线 | 总是先 `ping`，检查 `success` 字段 |

---

## 许可证

MIT License — Copyright (c) 2026 ZHANG-923-ZE

详见 [LICENSE](./LICENSE) 文件。
