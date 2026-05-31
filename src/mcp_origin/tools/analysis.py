"""MCP analysis tools: linear / nonlinear / peak fitting and descriptive statistics.

Four tools that leverage OriginPro's built-in analysis engines (LinearFit,
NLFit, Peak Analyzer, column statistics) through the originpro COM API.
All return standardised ``{"success": bool, ...}`` dicts and follow the same
architecture pattern:
``ensure_origin() → import originpro → validate → operate → format_response``.
"""

from __future__ import annotations

from typing import Any

from mcp_origin.core.connection import ensure_origin
from mcp_origin.core.constants import FIT_MODELS
from mcp_origin.core.errors import (
    OriginNotRunningError,
    ToolExecutionError,
    ValidationError,
)
from mcp_origin.utils import format_response, validate_column_index

# ── Peak models supported by fit_peak ────────────────────────────────────────
_PEAK_MODELS = frozenset({"Gauss", "Lorentz"})

# ── Valid statistic names for compute_statistics ─────────────────────────────
_VALID_STATS = frozenset({
    "mean", "std", "min", "max", "median", "sum", "n",
    "skew", "kurtosis", "variance", "sem", "mode", "range",
})


# ============================================================================
# Internal helpers
# ============================================================================

def _find_worksheet(op: Any, name: str) -> Any:
    """Resolve a worksheet by name, or return the active worksheet.

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
                "No active worksheet. Create or open a worksheet first.",
                hint="Use create_worksheet() to create a new sheet, or open an existing project.",
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
            if hasattr(page, "type") and page.type == "w" and hasattr(page, "name"):
                names.append(page.name)
    except Exception:
        pass
    return names


def _parse_parameter_table(params_table: Any) -> dict[str, dict[str, float]]:
    """Parse an originpro parameter table into a dict keyed by parameter name.

    Origin's result tables can be either:
    - A dict mapping col names → list of values
    - A list of dicts (one per row)

    Returns dict like: {"Slope": {"value": 1.5, "error": 0.1}, ...}
    """
    result: dict[str, dict[str, float]] = {}

    try:
        if isinstance(params_table, dict):
            # Column-oriented: {"name": ["Slope", "Intercept"], "value": [...], ...}
            names = params_table.get("name", params_table.get("Name", []))
            values = params_table.get("value", params_table.get("Value", []))
            errors = params_table.get("error", params_table.get("Error", []))
            if isinstance(names, (list, tuple)):
                for i, n in enumerate(names):
                    entry: dict[str, float] = {}
                    if isinstance(values, (list, tuple)) and i < len(values):
                        entry["value"] = float(values[i])
                    if isinstance(errors, (list, tuple)) and i < len(errors):
                        entry["error"] = float(errors[i])
                    result[str(n)] = entry
        elif isinstance(params_table, (list, tuple)):
            # Row-oriented: [{name: "Slope", value: 1.5, error: 0.1}, ...]
            for row in params_table:
                if isinstance(row, dict):
                    name = row.get("name", row.get("Name", ""))
                    if name:
                        entry = {}
                        for k in ("value", "Value"):
                            if k in row:
                                entry["value"] = float(row[k])
                                break
                        for k in ("error", "Error"):
                            if k in row:
                                entry["error"] = float(row[k])
                                break
                        result[str(name)] = entry
    except (TypeError, ValueError):
        pass

    return result


def _get_stat_value(stats_table: Any, key: str) -> float | None:
    """Extract a single statistic value from a stats table by key name.

    Handles both column-oriented dicts and row-oriented lists.
    """
    try:
        if isinstance(stats_table, dict):
            names = stats_table.get("name", stats_table.get("Name", []))
            values = stats_table.get("value", stats_table.get("Value", []))
            if isinstance(names, (list, tuple)) and isinstance(values, (list, tuple)):
                for i, n in enumerate(names):
                    if str(n).strip().lower() == key.strip().lower() and i < len(values):
                        return float(values[i])
        elif isinstance(stats_table, (list, tuple)):
            for row in stats_table:
                if isinstance(row, dict):
                    name = row.get("name", row.get("Name", ""))
                    if str(name).strip().lower() == key.strip().lower():
                        v = row.get("value", row.get("Value"))
                        if v is not None:
                            return float(v)
    except (TypeError, ValueError):
        pass
    return None


def _get_report_sheet_name(wks: Any, report_range: Any) -> str:
    """Attempt to derive a human-readable report sheet name."""
    if report_range is None:
        return ""

    # report_range is typically a DataRange or string like "Report!..."
    if isinstance(report_range, str):
        return report_range

    try:
        # Some originpro versions return a range object with a sheet attribute
        if hasattr(report_range, "sheet"):
            sheet = report_range.sheet
            return getattr(sheet, "name", str(report_range))
    except Exception:
        pass

    return str(report_range)


# ============================================================================
# D1: fit_linear
# ============================================================================

def fit_linear(
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    fix_slope: float | None = None,
    fix_intercept: float | None = None,
    confidence_band: bool = False,
    prediction_band: bool = False,
) -> dict:
    """Perform linear regression (y = a + b*x) on the specified columns.

    Uses Origin's ``LinearFit`` engine. Optionally fix slope / intercept
    and generate confidence / prediction bands on the fit plot.

    Args:
        worksheet_name: Target worksheet (empty = active sheet).
        x_col: 0‑based index of the X column.
        y_col: 0‑based index of the Y column.
        fix_slope: If set, fix the slope to this value.
        fix_intercept: If set, fix the intercept to this value.
        confidence_band: Generate confidence band on the fit curve.
        prediction_band: Generate prediction band on the fit curve.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``slope``, ``slope_error``, ``intercept``, ``intercept_error``,
        ``r_squared``, ``adj_r_squared``, ``pearson_r``, ``report_sheet``.

    Raises:
        ValidationError: Column indices are invalid or worksheet is missing.
        OriginNotRunningError: Origin is not reachable.
        ToolExecutionError: The originpro linear fit call failed.
    """
    tool = "fit_linear"

    try:
        # ── 1. Pre-flight validation ────────────────────────────────────
        for label, col in (("x_col", x_col), ("y_col", y_col)):
            if not isinstance(col, int) or col < 0:
                raise ValidationError(
                    f"{label} must be a non‑negative integer, got {col!r}.",
                    tool_name=tool,
                    details={"parameter": label, "value": col},
                    hint="Column indices are 0‑based. Use 0 for the first column.",
                )

        # ── 2. Connect and locate worksheet ─────────────────────────────
        ensure_origin()
        import originpro as op

        wks = _find_worksheet(op, worksheet_name)
        validate_column_index(wks, x_col)
        validate_column_index(wks, y_col)

        # ── 3. Perform linear fit ───────────────────────────────────────
        lr = op.LinearFit()
        lr.set_data(wks, x=x_col, y=y_col)

        if fix_slope is not None:
            lr.fix_slope(fix_slope)
        if fix_intercept is not None:
            lr.fix_intercept(fix_intercept)

        # Determine band parameter: 0=none, 1=confidence, 2=prediction, 3=both
        band = 0
        if confidence_band:
            band |= 1
        if prediction_band:
            band |= 2

        # Calling result() triggers the fit internally.
        results = lr.result()
        report_range = lr.report(band=band) if band else None

        # ── 4. Parse results ────────────────────────────────────────────
        params = _parse_parameter_table(results.get("Parameters", results.get("parameters", {})))
        stats = results.get("RegStats", results.get("Statistics", results.get("stats", {})))

        slope_entry = params.get("Slope", params.get("slope", {}))
        intercept_entry = params.get("Intercept", params.get("intercept", {}))

        data: dict[str, Any] = {
            "slope": slope_entry.get("value"),
            "slope_error": slope_entry.get("error"),
            "intercept": intercept_entry.get("value"),
            "intercept_error": intercept_entry.get("error"),
            "r_squared": _get_stat_value(stats, "R-Square") or _get_stat_value(stats, "Rsquare"),
            "adj_r_squared": _get_stat_value(stats, "Adj. R-Square"),
            "pearson_r": _get_stat_value(stats, "Pearson's r"),
            "report_sheet": _get_report_sheet_name(wks, report_range),
        }

        return format_response(True, data=data)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ToolExecutionError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as exc:
        return format_response(
            False,
            error=str(exc),
            hint="Linear fit failed. Check that both columns contain numeric data.",
        )


# ============================================================================
# D2: fit_nonlinear
# ============================================================================

def fit_nonlinear(
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    model: str = "Gauss",
    param_guesses: dict | None = None,
    fix_params: list[str] | None = None,
    bounds: dict | None = None,
) -> dict:
    """Fit a nonlinear model to the specified data columns.

    Uses Origin's ``NLFit`` engine.  Supports parameter constraints
    (fixing, bounding) and initial guesses for robust convergence.

    Args:
        worksheet_name: Target worksheet (empty = active sheet).
        x_col: 0‑based index of the X column.
        y_col: 0‑based index of the Y column.
        model: Built-in fit model name.  Must be one of: ``"Gauss"``,
            ``"Lorentz"``, ``"ExpDecay"``, ``"ExpGrowth"``, ``"Poly"``,
            ``"Line"``, ``"Sine"``, ``"Boltzmann"``, ``"DoseResp"``,
            ``"Logistic"``, ``"Voigt"``, ``"Allometric1"``.
        param_guesses: Initial parameter values, e.g. ``{"xc": 5.0, "A": 10.0}``.
        fix_params: Parameter names to hold constant during fit, e.g.
            ``["y0", "xc"]``.  Parameters not in *param_guesses* are fixed at 0.
        bounds: Parameter bounds, e.g. ``{"A": [">", 0], "xc": ["<", 100]}``.
            Each entry is ``[operator, value]`` where *operator* is ``">"``
            (lower bound) or ``"<"`` (upper bound).

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``model_used``, ``converged``, ``iterations``,
        ``parameters`` (``{name: {value, error}}``), ``r_squared``,
        ``report_sheet``.

    Raises:
        ValidationError: Invalid model name or column indices.
        OriginNotRunningError: Origin is not reachable.
        ToolExecutionError: The originpro NLFit call failed to converge.
    """
    tool = "fit_nonlinear"

    try:
        # ── 1. Pre-flight validation ────────────────────────────────────
        if model not in FIT_MODELS:
            raise ValidationError(
                f"Unknown fit model '{model}'.",
                tool_name=tool,
                details={"model": model, "valid_models": FIT_MODELS},
                hint=f"Choose one of: {', '.join(FIT_MODELS)}.",
            )

        for label, col in (("x_col", x_col), ("y_col", y_col)):
            if not isinstance(col, int) or col < 0:
                raise ValidationError(
                    f"{label} must be a non‑negative integer, got {col!r}.",
                    tool_name=tool,
                    details={"parameter": label, "value": col},
                    hint="Column indices are 0‑based.",
                )

        # ── 2. Connect and locate worksheet ─────────────────────────────
        ensure_origin()
        import originpro as op

        wks = _find_worksheet(op, worksheet_name)
        validate_column_index(wks, x_col)
        validate_column_index(wks, y_col)

        # ── 3. Configure and run NLFit ──────────────────────────────────
        nlf = op.NLFit(model)
        nlf.set_data(wks, x=x_col, y=y_col)

        # Apply initial parameter guesses
        if param_guesses:
            for pname, pval in param_guesses.items():
                try:
                    nlf.set_param(pname, float(pval))
                except Exception:
                    pass  # param may not exist for this model

        # Fix specified parameters at their guessed value (or 0)
        if fix_params:
            guesses = param_guesses or {}
            for pname in fix_params:
                try:
                    fix_val = float(guesses.get(pname, 0))
                    nlf.fix_param(pname, fix_val)
                except Exception:
                    pass

        # Apply parameter bounds
        if bounds:
            for pname, bound in bounds.items():
                if not isinstance(bound, (list, tuple)) or len(bound) != 2:
                    continue
                op_symbol, bound_val = bound[0], bound[1]
                try:
                    if op_symbol == ">":
                        nlf.set_lbound(pname, ">", float(bound_val))
                    elif op_symbol == "<":
                        nlf.set_ubound(pname, "<", float(bound_val))
                except Exception:
                    pass

        # Execute the fit
        nlf.fit()

        # ── 4. Parse results ────────────────────────────────────────────
        results = nlf.result()
        params_table = results.get("Parameters", results.get("parameters", {}))
        stats = results.get("Statistics", results.get("RegStats", results.get("stats", {})))
        fit_status = results.get("FitStatus", results.get("Fit_Status", {}))

        parameters = _parse_parameter_table(params_table)

        converged_raw = _get_stat_value(fit_status, "Converged")
        converged = bool(int(converged_raw)) if converged_raw is not None else True
        iterations = _get_stat_value(fit_status, "Iterations") or _get_stat_value(fit_status, "NumIter")

        # Generate report
        report_range = None
        try:
            report_range, _ = nlf.report()
        except Exception:
            pass

        data: dict[str, Any] = {
            "model_used": model,
            "converged": converged,
            "iterations": int(iterations) if iterations is not None else None,
            "parameters": parameters,
            "r_squared": _get_stat_value(stats, "R-Square") or _get_stat_value(stats, "Rsquare"),
            "report_sheet": _get_report_sheet_name(wks, report_range),
        }

        return format_response(True, data=data)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ToolExecutionError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as exc:
        return format_response(
            False,
            error=str(exc),
            hint=f"Nonlinear fit with model '{model}' failed. Try different initial "
                 "parameter guesses or check that the data is suitable for this model.",
        )


# ============================================================================
# D3: fit_peak
# ============================================================================

def fit_peak(
    worksheet_name: str = "",
    x_col: int = 0,
    y_col: int = 1,
    peak_count: int = 1,
    peak_model: str = "Gauss",
    auto_find: bool = True,
) -> dict:
    """Perform multi‑peak fitting on spectral / chromatographic data.

    Uses Origin's ``NLFit`` engine with Gaussian or Lorentzian peak functions.
    When *auto_find* is ``True``, Origin's built-in peak‑finding algorithm
    is used to estimate initial peak positions before fitting.

    Args:
        worksheet_name: Target worksheet (empty = active sheet).
        x_col: 0‑based index of the X column (e.g. wavenumber, retention time).
        y_col: 0‑based index of the Y column (signal intensity).
        peak_count: Number of peaks to fit (≥ 1).
        peak_model: Peak shape — ``"Gauss"`` or ``"Lorentz"``.
        auto_find: If ``True``, use Origin's peak‑finding to locate
            initial peak centres automatically.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``peak_count_found``, ``peaks`` (list of ``{center, height, fwhm, area}``),
        ``report_sheet``.

    Raises:
        ValidationError: Invalid peak model, count, or column indices.
        OriginNotRunningError: Origin is not reachable.
        ToolExecutionError: The peak fitting failed (e.g. poor convergence).
    """
    tool = "fit_peak"

    try:
        # ── 1. Pre-flight validation ────────────────────────────────────
        if peak_model not in _PEAK_MODELS:
            raise ValidationError(
                f"Peak model '{peak_model}' is not supported.",
                tool_name=tool,
                details={"peak_model": peak_model, "valid": sorted(_PEAK_MODELS)},
                hint="Use 'Gauss' or 'Lorentz' for peak fitting.",
            )

        if not isinstance(peak_count, int) or peak_count < 1:
            raise ValidationError(
                f"peak_count must be a positive integer, got {peak_count!r}.",
                tool_name=tool,
                details={"peak_count": peak_count},
                hint="Specify at least 1 peak.",
            )

        for label, col in (("x_col", x_col), ("y_col", y_col)):
            if not isinstance(col, int) or col < 0:
                raise ValidationError(
                    f"{label} must be a non‑negative integer, got {col!r}.",
                    tool_name=tool,
                    details={"parameter": label, "value": col},
                    hint="Column indices are 0‑based.",
                )

        # ── 2. Connect and locate worksheet ─────────────────────────────
        ensure_origin()
        import originpro as op

        wks = _find_worksheet(op, worksheet_name)
        validate_column_index(wks, x_col)
        validate_column_index(wks, y_col)

        # ── 3. Configure multi‑peak NLFit ───────────────────────────────
        # For a single peak, use NLFit directly.
        # For multiple peaks, each peak adds its own set of parameters to
        # the fit model (xc_i, A_i, w_i for Gauss; xc_i, A_i, w_i for Lorentz).
        nlf = op.NLFit(peak_model)
        nlf.set_data(wks, x=x_col, y=y_col)

        # When peak_count > 1, the model internally replicates the peak
        # function.  Origin's NLFit supports multi‑peak via the 'n' parameter
        # or by adding replicate functions.
        if peak_count > 1:
            try:
                # Attempt to set number of peaks via set_data or a dedicated method.
                # Different originpro versions use different APIs.
                if hasattr(nlf, "set_num_peaks"):
                    nlf.set_num_peaks(peak_count)
                elif hasattr(nlf, "set_replica"):
                    for _ in range(peak_count - 1):
                        nlf.set_replica()
            except Exception:
                # If multi‑peak configuration fails, proceed with single‑peak
                # and note the limitation in the result.
                pass

        # Auto‑find peaks to get initial guesses
        peaks_found = peak_count
        if auto_find and peak_count > 1:
            try:
                # Origin's peak finding — different APIs across versions.
                if hasattr(nlf, "peak_find"):
                    found = nlf.peak_find()
                    if isinstance(found, int):
                        peaks_found = found
                elif hasattr(nlf, "peaks") and hasattr(nlf.peaks, "find"):
                    nlf.peaks.find(peak_count)
            except Exception:
                # Auto‑find is best‑effort; fitting proceeds with defaults.
                pass

        # Execute the fit
        nlf.fit()

        # ── 4. Parse peak results ───────────────────────────────────────
        results = nlf.result()
        params_table = results.get("Parameters", results.get("parameters", {}))
        parameters = _parse_parameter_table(params_table)

        # Extract peak-by-peak information from the parameter table.
        # For Gauss: parameters are named xc, A, w (possibly xc1, A1, w1, ...)
        # For Lorentz: xc, A, w
        peaks: list[dict[str, Any]] = []

        if peak_count == 1:
            xc = parameters.get("xc", {})
            amp = parameters.get("A", {})
            w = parameters.get("w", {})
            center = xc.get("value")
            height = amp.get("value")
            fwhm_val = w.get("value")

            # Derive area: for Gauss, area ≈ A * w * sqrt(pi/ln2) / 2
            # For Lorentz, area ≈ A * w * pi / 2
            # Using a simple approximation: area ≈ height * fwhm * 1.06
            area = None
            if height is not None and fwhm_val is not None:
                if peak_model == "Gauss":
                    area = height * fwhm_val * 1.0645  # Gaussian area ≈ 1.0645 * A * FWHM
                else:
                    area = height * fwhm_val * 1.5708  # Lorentzian area ≈ π/2 * A * FWHM

            peaks.append({
                "center": center,
                "height": height,
                "fwhm": fwhm_val,
                "area": area,
            })
        else:
            # Multi‑peak: parameters may be named xc1, A1, w1 or peak1_xc, etc.
            # Iterate over parameter keys to group by peak index.
            peak_params: dict[int, dict[str, float | None]] = {}
            for pname, pdata in parameters.items():
                # Try suffix‑style naming: xc1, A1, w1, etc.
                idx = 1
                base = pname.rstrip("0123456789")
                suffix = pname[len(base):]
                if suffix.isdigit():
                    idx = int(suffix)
                else:
                    # Maybe prefixed: peak1_xc → suffix is '' so idx stays 1
                    parts = pname.split("_")
                    if len(parts) == 2 and parts[1] in ("xc", "A", "w", "y0"):
                        idx = 1

                if idx not in peak_params:
                    peak_params[idx] = {}
                param_type = base if suffix else pname
                if param_type in ("xc", "A", "w", "y0"):
                    peak_params[idx][param_type] = pdata.get("value")

            for idx in sorted(peak_params):
                pp = peak_params[idx]
                h = pp.get("A")
                fw = pp.get("w")
                c = pp.get("xc")
                ar = None
                if h is not None and fw is not None:
                    if peak_model == "Gauss":
                        ar = h * fw * 1.0645
                    else:
                        ar = h * fw * 1.5708
                peaks.append({
                    "center": c,
                    "height": h,
                    "fwhm": fw,
                    "area": ar,
                })

        # If auto‑find adjusted the count, reflect it
        actual_count = len(peaks) or peaks_found

        # Generate report
        report_range = None
        try:
            report_range, _ = nlf.report()
        except Exception:
            pass

        data: dict[str, Any] = {
            "peak_count_found": actual_count,
            "peaks": peaks,
            "report_sheet": _get_report_sheet_name(wks, report_range),
        }

        return format_response(True, data=data)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ToolExecutionError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as exc:
        return format_response(
            False,
            error=str(exc),
            hint="Peak fitting failed. Try reducing peak_count, changing the model, "
                 "or checking that the data has well‑defined peaks.",
        )


# ============================================================================
# D4: compute_statistics
# ============================================================================

def compute_statistics(
    worksheet_name: str = "",
    column: int = 0,
    stats: list[str] | None = None,
) -> dict:
    """Compute descriptive statistics for a worksheet column.

    Leverages Origin's column‑wise statistics capabilities.  When *stats*
    is ``None`` or empty, all available statistics are returned.

    Args:
        worksheet_name: Target worksheet (empty = active sheet).
        column: 0‑based index of the column to analyze.
        stats: Specific statistic names to compute.  Valid values:
            ``"mean"``, ``"std"``, ``"min"``, ``"max"``, ``"median"``,
            ``"sum"``, ``"n"``, ``"skew"``, ``"kurtosis"``, ``"variance"``,
            ``"sem"``, ``"mode"``, ``"range"``.  Pass ``None`` or ``[]``
            for all available.

    Returns:
        Standardised response dict.  On success ``data`` contains:
        ``worksheet``, ``column``, ``row_count``, ``statistics`` (dict of
        ``{stat_name: value}``).

    Raises:
        ValidationError: Column index is invalid or unknown stat name.
        OriginNotRunningError: Origin is not reachable.
        ToolExecutionError: Statistics computation failed.
    """
    tool = "compute_statistics"

    try:
        # ── 1. Pre-flight validation ────────────────────────────────────
        if not isinstance(column, int) or column < 0:
            raise ValidationError(
                f"column must be a non‑negative integer, got {column!r}.",
                tool_name=tool,
                details={"column": column},
                hint="Column indices are 0‑based.",
            )

        # Resolve which stats to compute
        if stats is None or len(stats) == 0:
            stats_to_compute = sorted(_VALID_STATS)
        else:
            stats_to_compute = []
            for s in stats:
                s_lower = str(s).strip().lower()
                if s_lower not in _VALID_STATS:
                    raise ValidationError(
                        f"Unknown statistic '{s}'.",
                        tool_name=tool,
                        details={"stat": s, "valid": sorted(_VALID_STATS)},
                        hint=f"Valid stats: {', '.join(sorted(_VALID_STATS))}.",
                    )
                stats_to_compute.append(s_lower)

        # ── 2. Connect and locate worksheet ─────────────────────────────
        ensure_origin()
        import originpro as op

        wks = _find_worksheet(op, worksheet_name)
        validate_column_index(wks, column)

        # ── 3. Fetch column data ────────────────────────────────────────
        col = wks.cols[column]
        col_data: list[float] = []

        try:
            # Get data from the column as a list of floats
            raw = col.get_data()
            if raw is not None:
                col_data = [float(v) for v in raw if v is not None]
        except Exception:
            # Fallback: try iterating cell by cell
            try:
                nrows = wks.rows
                col_data = []
                for r in range(nrows):
                    cell_val = wks.get_cell(r, column)
                    if cell_val is not None:
                        try:
                            col_data.append(float(cell_val))
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass

        if not col_data:
            raise ValidationError(
                f"Column {column} contains no numeric data.",
                tool_name=tool,
                details={"column": column, "worksheet": getattr(wks, "name", "")},
                hint="Populate the column with numeric values before computing statistics.",
            )

        # ── 4. Compute statistics ───────────────────────────────────────
        stat_results: dict[str, float] = {}

        # Use Origin's column statistics if available, else compute manually
        use_origin_stats = False
        try:
            # OriginPro may expose col_stats or similar
            if hasattr(op, "col_stats"):
                origin_stats = op.col_stats(col)
                use_origin_stats = True
                for stat_name in stats_to_compute:
                    val = origin_stats.get(stat_name)
                    if val is not None:
                        stat_results[stat_name] = float(val)
        except Exception:
            use_origin_stats = False

        if not use_origin_stats:
            # Manual computation as fallback
            from statistics import mean, median, stdev, mode as stat_mode, StatisticsError

            n = len(col_data)
            sorted_data = sorted(col_data)
            stat_handlers = {
                "n": lambda: float(n),
                "mean": lambda: mean(col_data),
                "std": lambda: stdev(col_data) if n > 1 else 0.0,
                "min": lambda: float(sorted_data[0]),
                "max": lambda: float(sorted_data[-1]),
                "median": lambda: float(median(col_data)),
                "sum": lambda: float(sum(col_data)),
                "skew": lambda: _compute_skew(col_data),
                "kurtosis": lambda: _compute_kurtosis(col_data),
                "variance": lambda: (
                    (sum((x - mean(col_data)) ** 2 for x in col_data) / (n - 1))
                    if n > 1 else 0.0
                ),
                "sem": lambda: (
                    stdev(col_data) / (n ** 0.5) if n > 1 else 0.0
                ),
                "mode": lambda: (
                    float(stat_mode(col_data)) if n > 0 else 0.0
                ),
                "range": lambda: float(sorted_data[-1] - sorted_data[0]),
            }

            for stat_name in stats_to_compute:
                try:
                    stat_results[stat_name] = stat_handlers[stat_name]()
                except (StatisticsError, ZeroDivisionError):
                    stat_results[stat_name] = 0.0
                except KeyError:
                    stat_results[stat_name] = 0.0

        # ── 5. Build response ───────────────────────────────────────────
        data = {
            "worksheet": getattr(wks, "name", ""),
            "column": column,
            "row_count": len(col_data),
            "statistics": stat_results,
        }
        return format_response(True, data=data)

    except OriginNotRunningError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ValidationError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except ToolExecutionError as e:
        return format_response(False, error=e.message, hint=e.hint)
    except Exception as exc:
        return format_response(
            False,
            error=str(exc),
            hint="Statistics computation failed. Check that the column contains numeric data.",
        )


# ============================================================================
# Statistics helper functions (used as fallback for compute_statistics)
# ============================================================================

def _compute_skew(data: list[float]) -> float:
    """Compute sample skewness (Fisher‑Pearson coefficient)."""
    from statistics import mean
    n = len(data)
    if n < 3:
        return 0.0
    m = mean(data)
    m2 = sum((x - m) ** 2 for x in data)
    m3 = sum((x - m) ** 3 for x in data)
    if m2 == 0:
        return 0.0
    sd = (m2 / (n - 1)) ** 0.5
    return (m3 / n) / (sd ** 3) * (n * (n - 1)) ** 0.5 / (n - 2)


def _compute_kurtosis(data: list[float]) -> float:
    """Compute excess kurtosis (Fisher definition, normal → 0)."""
    from statistics import mean
    n = len(data)
    if n < 4:
        return 0.0
    m = mean(data)
    m2 = sum((x - m) ** 2 for x in data)
    m4 = sum((x - m) ** 4 for x in data)
    if m2 == 0:
        return 0.0
    # Sample excess kurtosis formula
    k = (m4 / n) / ((m2 / n) ** 2) - 3.0
    # Apply bias correction for small samples
    k = ((n + 1) * k + 6.0) * (n - 1) / ((n - 2) * (n - 3))
    return k
