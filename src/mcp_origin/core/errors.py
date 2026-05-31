"""Structured exception hierarchy for MCP OriginPro server.

All exceptions expose `message`, `tool_name`, `details`, and `hint` attributes
so the MCP layer can produce consistent, actionable error responses.
"""

from __future__ import annotations

from typing import Any


class OriginProError(Exception):
    """Base exception for all OriginPro MCP errors.

    Attributes:
        message: Human-readable error summary.
        tool_name: Name of the MCP tool that raised the error (if applicable).
        details: Machine-readable extra context (e.g. the invalid parameter value).
        hint: Actionable suggestion for the LLM / end user.
    """

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        details: Any = None,
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.tool_name = tool_name
        self.details = details
        self.hint = hint

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a dict suitable for JSON error responses."""
        d: dict[str, Any] = {
            "error": self.message,
            "type": self.__class__.__name__,
        }
        if self.tool_name:
            d["tool"] = self.tool_name
        if self.details is not None:
            d["details"] = self.details
        if self.hint:
            d["hint"] = self.hint
        return d


class OriginNotRunningError(OriginProError):
    """Raised when Origin / OriginPro is not running (COM unavailable).

    The connection layer should raise this *before* attempting any Origin API call.
    """

    def __init__(
        self,
        message: str = "OriginPro is not running or its COM server is unavailable.",
        *,
        tool_name: str = "",
        details: Any = None,
        hint: str = (
            "Please launch OriginPro 2025b before using the MCP tools. "
            "If Origin is already running, check that COM automation is enabled "
            "(Tools → System Variables → opj_allow_automation=1)."
        ),
    ) -> None:
        super().__init__(message, tool_name=tool_name, details=details, hint=hint)


class ToolExecutionError(OriginProError):
    """Raised when an originpro API call fails at runtime.

    Wraps the underlying exception so the MCP layer can surface the cause
    without leaking raw tracebacks.
    """

    def __init__(
        self,
        message: str = "An originpro operation failed.",
        *,
        tool_name: str = "",
        details: Any = None,
        hint: str = "",
    ) -> None:
        super().__init__(message, tool_name=tool_name, details=details, hint=hint)

    @classmethod
    def from_exc(
        cls,
        exc: Exception,
        *,
        tool_name: str = "",
        hint: str = "",
    ) -> "ToolExecutionError":
        """Convenience constructor that wraps an arbitrary exception."""
        return cls(
            str(exc),
            tool_name=tool_name,
            details={"exception_type": type(exc).__name__},
            hint=hint,
        )


class ValidationError(OriginProError):
    """Raised when tool parameters fail pre-flight validation.

    The `details` dict should contain the offending parameter name and value
    so the LLM can self-correct on retry.
    """

    def __init__(
        self,
        message: str = "Parameter validation failed.",
        *,
        tool_name: str = "",
        details: Any = None,
        hint: str = "",
    ) -> None:
        super().__init__(message, tool_name=tool_name, details=details, hint=hint)
