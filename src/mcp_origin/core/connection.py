"""Origin COM connection management — detection, lazy init, and lifecycle.

All public functions in this module are designed to be safe to call at any time.
They never leak raw COM tracebacks; instead they raise structured
:class:`~mcp_origin.core.errors.OriginNotRunningError` instances.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from mcp_origin.core.errors import OriginNotRunningError

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)

# Module-level sentinel that holds the lazily-imported originpro module.
# None   = never tried
# False  = tried but failed (Origin not available)
# module = successfully imported
_originpro: ModuleType | bool | None = None

# Lazy reference to the Origin COM application object (op.oext).
_app: Any = None

# Standard Origin 2025b installation paths (Windows only).
_KNOWN_ORIGIN_DIRS = (
    r"C:\Program Files\OriginLab\Origin2025b",
    r"C:\Program Files (x86)\OriginLab\Origin2025b",
)


def is_originpro_installed() -> bool:
    """Return ``True`` if the ``originpro`` Python package can be imported.

    This is a lightweight check — it does not connect to Origin COM,
    only verifies the package is on ``sys.path``.  Use this to
    distinguish "package not installed" from "Origin not running".
    """
    global _originpro  # noqa: PLW0603
    if _originpro is None:
        _originpro = _try_import_originpro() or False
    return _originpro is not False


def get_origin_status() -> dict[str, Any]:
    """Return a structured dict describing the current Origin connectivity.

    The result always includes ``status`` (one of ``"connected"``,
    ``"origin_not_running"``, ``"originpro_not_installed"``) and
    ``hint`` with an actionable suggestion.

    Returns:
        A dict with keys: ``status``, ``hint``, ``originpro_installed``,
        ``origin_install_path`` (if found).
    """
    result: dict[str, Any] = {
        "originpro_installed": is_originpro_installed(),
    }

    if not result["originpro_installed"]:
        # Try to find Origin installation for a better hint.
        for candidate in _KNOWN_ORIGIN_DIRS:
            if os.path.isdir(candidate):
                result["origin_install_path"] = candidate
                break

        result["status"] = "originpro_not_installed"
        if result.get("origin_install_path"):
            result["hint"] = (
                "Origin 2025b is installed but the originpro Python package "
                "is not on sys.path. Try adding the Origin Python directory "
                "to sys.path or re-installing Origin with Python support."
            )
        else:
            result["hint"] = (
                "The originpro Python package is not installed. "
                "Install Origin 2025b first, then ensure originpro is "
                "on your Python path (typically under Origin's Python directory)."
            )
        return result

    # originpro is installed — check COM connectivity.
    if is_origin_running():
        result["status"] = "connected"
        result["hint"] = ""
        return result

    result["status"] = "origin_not_running"
    result["hint"] = (
        "Origin 2025b is NOT running or COM automation is disabled. "
        "Please launch Origin 2025b. If already running, check "
        "Tools → System Variables → opj_allow_automation=1, then restart Origin."
    )
    return result


def _try_import_originpro() -> ModuleType | None:
    """Attempt to import originpro; return the module or None on failure.

    An apparently successful import does **not** guarantee that Origin is
    actually running — originpro may load but yield a COM stub.  The caller
    must still check ``_app`` (or ``op.oext``) for a live connection.
    """
    try:
        import originpro as op  # type: ignore[import-untyped]
        return op
    except (ImportError, OSError) as exc:
        logger.debug("originpro import failed: %s", exc)
        logger.warning(
            "The `originpro` package is not installed. "
            "It ships with Origin 2025b and is NOT available on PyPI. "
            "Install Origin 2025b with Python support, then ensure "
            "originpro is on your Python path."
        )
        return None


def is_origin_running() -> bool:
    """Return ``True`` if Origin is running and accessible via COM.

    Uses ``originpro.get_show()`` to detect an active Origin COM connection.
    On first successful connection, caches the originpro module as ``_app``
    for use by ``get_origin_app()``.

    This function imports originpro at most once per process lifetime.
    """
    global _originpro, _app  # noqa: PLW0603

    if _originpro is None:
        _originpro = _try_import_originpro() or False

    if _originpro is False:
        return False

    op = _originpro

    # Already connected?  Check cached connection state.
    if _app is not None:
        try:
            if op.get_show():
                return True
        except Exception:
            _app = None  # connection lost — reset
            return False

    # originpro 1.1.15+: oext is a bool (True = external Python mode).
    # get_show() tells if we're attached to a running Origin instance.
    try:
        if op.get_show():
            _app = op  # cache the module as app reference
            return True

        # Not yet attached — try connecting to running Origin.
        op.attach()
        if op.get_show():
            _app = op
            return True
        return False
    except Exception:
        return False


def ensure_origin() -> None:
    """Verify that Origin is running; raise :class:`OriginNotRunningError` if not.

    Call this at the top of every MCP tool that needs an Origin COM session.
    The raised exception includes a differentiated ``hint`` depending on whether
    the ``originpro`` package is missing vs. Origin COM is unavailable.
    """
    status = get_origin_status()
    if status["status"] == "connected":
        return

    if status["status"] == "originpro_not_installed":
        raise OriginNotRunningError(
            message="originpro Python package is not installed — cannot connect to Origin.",
            details={"status_info": status},
            hint=status["hint"],
        )

    raise OriginNotRunningError(
        message="Origin 2025b is not running or its COM server is unavailable.",
        details={"status_info": status},
        hint=status["hint"],
    )


def get_origin_app() -> Any:
    """Return the originpro module (cached after successful COM connection).

    In originpro 1.1.15+, the module itself serves as the application entry
    point — all operations go through ``op.new_sheet()``, ``op.new_graph()``,
    etc.  This replaces the older pattern of using ``op.oext`` as a COM object.

    Returns:
        The originpro module.

    Raises:
        OriginNotRunningError: Origin is not running or COM is unavailable.
    """
    global _app  # noqa: PLW0603

    ensure_origin()
    # _app is set to the op module inside is_origin_running() on success.
    assert _app is not None, "ensure_origin() passed but _app is still None — logic bug"
    return _app


def reset_connection() -> None:
    """Reset the cached originpro module and app reference.

    Useful in test suites where the COM state may change between runs.
    Not normally needed in production.
    """
    global _originpro, _app  # noqa: PLW0603
    _originpro = None
    _app = None
    logger.debug("Origin COM connection cache reset.")
