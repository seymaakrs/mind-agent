"""Structured error classification for all external service integrations.

This module provides:
- ServiceError: RuntimeError subclass that carries HTTP status codes and service names
- ErrorCode: String enum for machine-readable error categories
- classify_error(): Converts any exception into a structured error dict
- classify_late_response(): Enriches Late API error dicts with structured fields

Usage in tools:
    from src.infra.errors import classify_error, classify_late_response

    # Exception-based services (Google AI, Kling, Firebase, fal.ai, Serper):
    except Exception as exc:
        return classify_error(exc, "google_ai")

    # Dict-based services (Late API):
    if not result.get("success"):
        return classify_late_response(result, "late")
"""
from __future__ import annotations

import re
from enum import StrEnum


# ---------------------------------------------------------------------------
# ServiceError — RuntimeError subclass with metadata
# ---------------------------------------------------------------------------


class ServiceError(RuntimeError):
    """Exception that carries structured error metadata.

    Extends RuntimeError so all existing ``except RuntimeError`` and
    ``except Exception`` blocks continue to catch it without changes.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        service: str | None = None,
        error_code_hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.service = service
        self.error_code_hint = error_code_hint


# ---------------------------------------------------------------------------
# ErrorCode enum
# ---------------------------------------------------------------------------


class ErrorCode(StrEnum):
    """Machine-readable error categories used across all services."""

    RATE_LIMIT = "RATE_LIMIT"
    SERVER_ERROR = "SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    CONTENT_POLICY = "CONTENT_POLICY"
    AUTH_ERROR = "AUTH_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Turkish user-facing messages
# ---------------------------------------------------------------------------

_USER_MESSAGES_TR: dict[ErrorCode, str] = {
    ErrorCode.RATE_LIMIT: "Servis şu an yoğun, kısa süre sonra tekrar denenecek.",
    ErrorCode.SERVER_ERROR: "Serviste geçici bir sorun oluştu, tekrar deneniyor.",
    ErrorCode.TIMEOUT: "İşlem zaman aşımına uğradı, tekrar deneniyor.",
    ErrorCode.CONTENT_POLICY: (
        "İçerik politikası nedeniyle işlem reddedildi. "
        "Lütfen farklı bir içerik veya prompt deneyin."
    ),
    ErrorCode.AUTH_ERROR: "Yetkilendirme hatası oluştu. Yönetici bilgilendirildi.",
    ErrorCode.INVALID_INPUT: "Geçersiz istek parametreleri. Lütfen girdiyi kontrol edin.",
    ErrorCode.INSUFFICIENT_BALANCE: (
        "Servis bakiyesi yetersiz. Yönetici bilgilendirildi."
    ),
    ErrorCode.NOT_FOUND: "İstenen kaynak bulunamadı.",
    ErrorCode.PERMISSION_DENIED: "Bu işlem için yetki yok. Yönetici bilgilendirildi.",
    ErrorCode.NETWORK_ERROR: "Ağ bağlantısı sorunu oluştu, tekrar deneniyor.",
    ErrorCode.UNKNOWN: "Beklenmeyen bir hata oluştu. Yönetici bilgilendirildi.",
}


# ---------------------------------------------------------------------------
# Service-specific mapping tables
# (status_code) -> (ErrorCode, retryable, retry_after_seconds)
# ---------------------------------------------------------------------------

_GOOGLE_AI_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    400: (ErrorCode.INVALID_INPUT, False, None),
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    404: (ErrorCode.NOT_FOUND, False, None),
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
    503: (ErrorCode.SERVER_ERROR, True, 30),
    504: (ErrorCode.TIMEOUT, True, 15),
}

# Kling uses API-level codes (1000-5002), not just HTTP status codes
_KLING_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    # Auth errors (1000-1004)
    1000: (ErrorCode.AUTH_ERROR, False, None),
    1001: (ErrorCode.AUTH_ERROR, False, None),
    1002: (ErrorCode.AUTH_ERROR, False, None),
    1003: (ErrorCode.AUTH_ERROR, True, 5),      # token not yet valid
    1004: (ErrorCode.AUTH_ERROR, True, 5),      # token expired, regenerate
    # Account/billing (1100-1103)
    1100: (ErrorCode.AUTH_ERROR, False, None),          # account suspended
    1101: (ErrorCode.INSUFFICIENT_BALANCE, False, None),
    1102: (ErrorCode.INSUFFICIENT_BALANCE, False, None),  # resource expired
    1103: (ErrorCode.PERMISSION_DENIED, False, None),
    # Invalid request (1200-1203)
    1200: (ErrorCode.INVALID_INPUT, False, None),
    1201: (ErrorCode.INVALID_INPUT, False, None),
    1202: (ErrorCode.NOT_FOUND, False, None),
    1203: (ErrorCode.NOT_FOUND, False, None),
    # Policy/rate limit (1300-1304)
    1300: (ErrorCode.CONTENT_POLICY, False, None),
    1301: (ErrorCode.CONTENT_POLICY, False, None),
    1302: (ErrorCode.RATE_LIMIT, True, 60),
    1303: (ErrorCode.RATE_LIMIT, True, 60),
    1304: (ErrorCode.AUTH_ERROR, False, None),    # IP whitelist
    # Server errors (5000-5002)
    5000: (ErrorCode.SERVER_ERROR, True, 30),
    5001: (ErrorCode.SERVER_ERROR, True, 30),
    5002: (ErrorCode.TIMEOUT, True, 15),
    # HTTP-level errors (fallback if Kling returns plain HTTP errors)
    400: (ErrorCode.INVALID_INPUT, False, None),
    401: (ErrorCode.AUTH_ERROR, False, None),
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
    503: (ErrorCode.SERVER_ERROR, True, 30),
}

_LATE_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    400: (ErrorCode.INVALID_INPUT, False, None),
    401: (ErrorCode.AUTH_ERROR, False, None),
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    404: (ErrorCode.NOT_FOUND, False, None),
    409: (ErrorCode.INVALID_INPUT, False, None),
    424: (ErrorCode.SERVER_ERROR, False, None),
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
    503: (ErrorCode.SERVER_ERROR, True, 30),
}

# Keyed by exception class name from google.api_core.exceptions
_FIREBASE_MAP: dict[str, tuple[ErrorCode, bool, int | None]] = {
    "ResourceExhausted": (ErrorCode.RATE_LIMIT, True, 60),
    "TooManyRequests": (ErrorCode.RATE_LIMIT, True, 60),
    "ServiceUnavailable": (ErrorCode.SERVER_ERROR, True, 30),
    "InternalServerError": (ErrorCode.SERVER_ERROR, True, 30),
    "Unknown": (ErrorCode.SERVER_ERROR, True, 30),
    "DeadlineExceeded": (ErrorCode.TIMEOUT, True, 15),
    "GatewayTimeout": (ErrorCode.TIMEOUT, True, 15),
    "NotFound": (ErrorCode.NOT_FOUND, False, None),
    "PermissionDenied": (ErrorCode.PERMISSION_DENIED, False, None),
    "Forbidden": (ErrorCode.PERMISSION_DENIED, False, None),
    "Unauthenticated": (ErrorCode.AUTH_ERROR, False, None),
    "InvalidArgument": (ErrorCode.INVALID_INPUT, False, None),
    "FailedPrecondition": (ErrorCode.INVALID_INPUT, False, None),
    "AlreadyExists": (ErrorCode.INVALID_INPUT, False, None),
    "Aborted": (ErrorCode.SERVER_ERROR, True, 5),  # transaction contention
    "DataLoss": (ErrorCode.SERVER_ERROR, False, None),
    "Cancelled": (ErrorCode.UNKNOWN, False, None),
}

_FAL_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    422: (ErrorCode.CONTENT_POLICY, False, None),  # validation/content errors
    500: (ErrorCode.SERVER_ERROR, True, 30),
    502: (ErrorCode.SERVER_ERROR, False, None),
    503: (ErrorCode.SERVER_ERROR, True, 30),
    504: (ErrorCode.TIMEOUT, True, 15),
}

_SERPER_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    400: (ErrorCode.INVALID_INPUT, False, None),
    401: (ErrorCode.AUTH_ERROR, False, None),
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
}

# NocoDB v2 REST API status codes
_NOCODB_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    400: (ErrorCode.INVALID_INPUT, False, None),
    401: (ErrorCode.AUTH_ERROR, False, None),
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    404: (ErrorCode.NOT_FOUND, False, None),
    409: (ErrorCode.INVALID_INPUT, False, None),  # duplicate / version conflict
    422: (ErrorCode.INVALID_INPUT, False, None),  # validation
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
    502: (ErrorCode.SERVER_ERROR, True, 30),
    503: (ErrorCode.SERVER_ERROR, True, 30),
    504: (ErrorCode.TIMEOUT, True, 15),
}

# Clay (B2B prospecting) status codes — generic HTTP, no Clay-specific codes yet
_CLAY_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    400: (ErrorCode.INVALID_INPUT, False, None),
    401: (ErrorCode.AUTH_ERROR, False, None),
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    404: (ErrorCode.NOT_FOUND, False, None),
    422: (ErrorCode.INVALID_INPUT, False, None),
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
    502: (ErrorCode.SERVER_ERROR, True, 30),
    503: (ErrorCode.SERVER_ERROR, True, 30),
    504: (ErrorCode.TIMEOUT, True, 15),
}

# Zernio unified social media API status codes
_ZERNIO_MAP: dict[int, tuple[ErrorCode, bool, int | None]] = {
    400: (ErrorCode.INVALID_INPUT, False, None),
    401: (ErrorCode.AUTH_ERROR, False, None),
    402: (ErrorCode.INSUFFICIENT_BALANCE, False, None),  # add-on not enabled
    403: (ErrorCode.PERMISSION_DENIED, False, None),
    404: (ErrorCode.NOT_FOUND, False, None),
    409: (ErrorCode.INVALID_INPUT, False, None),
    422: (ErrorCode.INVALID_INPUT, False, None),
    429: (ErrorCode.RATE_LIMIT, True, 60),
    500: (ErrorCode.SERVER_ERROR, True, 30),
    502: (ErrorCode.SERVER_ERROR, True, 30),
    503: (ErrorCode.SERVER_ERROR, True, 30),
    504: (ErrorCode.TIMEOUT, True, 15),
}

_SERVICE_MAPS: dict[str, dict] = {
    "google_ai": _GOOGLE_AI_MAP,
    "kling": _KLING_MAP,
    "late": _LATE_MAP,
    "fal_ai": _FAL_MAP,
    "serper": _SERPER_MAP,
    "nocodb": _NOCODB_MAP,
    "zernio": _ZERNIO_MAP,
    "clay": _CLAY_MAP,
    # firebase uses class-name based map, handled separately
}


# ---------------------------------------------------------------------------
# Regex helpers for legacy RuntimeError messages
# ---------------------------------------------------------------------------

# Matches "API Error 429:" or "Kling API Error 503:"
_RE_HTTP_STATUS = re.compile(r"API Error (\d{3}):")

# Matches "Kling API Error code=1101:"
_RE_KLING_CODE = re.compile(r"Kling API Error code=(\d+):")


def _extract_status_code(exc_str: str) -> int | None:
    """Extract HTTP status code or Kling API code from legacy error messages."""
    m = _RE_KLING_CODE.search(exc_str)
    if m:
        return int(m.group(1))
    m = _RE_HTTP_STATUS.search(exc_str)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Public API: classify_error
# ---------------------------------------------------------------------------


def classify_error(
    exc: Exception,
    service: str,
    status_code: int | None = None,
) -> dict:
    """Classify any exception into a structured error dict.

    The returned dict always contains both legacy fields (``success``,
    ``error``) for backward compatibility and new structured fields
    (``error_code``, ``retryable``, etc.) for agent-driven retry logic.

    Args:
        exc: The caught exception.
        service: Service identifier (``"google_ai"``, ``"kling"``,
            ``"late"``, ``"firebase"``, ``"fal_ai"``, ``"serper"``).
        status_code: Optional explicit status code override.

    Returns:
        Structured error dict.
    """
    # 1. Determine status code from various sources
    code = status_code
    if code is None and isinstance(exc, ServiceError):
        code = exc.status_code
        service = exc.service or service
    if code is None and hasattr(exc, "code"):
        code = getattr(exc, "code", None)
    if code is None:
        code = _extract_status_code(str(exc))

    # 2. Check for error_code_hint (e.g., CONTENT_POLICY from safety filter)
    hint = getattr(exc, "error_code_hint", None)
    if hint:
        error_code = ErrorCode(hint)
        retryable = False
        retry_after: int | None = None
    # 3. Check exception type for common patterns
    elif isinstance(exc, TimeoutError):
        error_code = ErrorCode.TIMEOUT
        retryable = True
        retry_after = 15
    elif isinstance(exc, ConnectionError):
        error_code = ErrorCode.NETWORK_ERROR
        retryable = True
        retry_after = 10
    # 4. Firebase: match by exception class name
    elif service == "firebase" and _classify_by_class_name(exc) is not None:
        error_code, retryable, retry_after = _classify_by_class_name(exc)
    # 5. Use service-specific mapping by status code
    elif code is not None and service in _SERVICE_MAPS:
        mapping = _SERVICE_MAPS[service]
        if code in mapping:
            error_code, retryable, retry_after = mapping[code]
        else:
            error_code, retryable, retry_after = _fallback_by_status(code)
    else:
        error_code = ErrorCode.UNKNOWN
        retryable = False
        retry_after = None

    # 6. Build the structured dict
    error_str = f"{type(exc).__name__}: {exc}"
    technical = f"HTTP {code}: {exc}" if code else error_str

    return {
        # Backward compat fields
        "success": False,
        "error": error_str,
        # New structured fields
        "error_code": error_code,
        "service": service,
        "retryable": retryable,
        "retry_after_seconds": retry_after,
        "user_message_tr": _USER_MESSAGES_TR.get(error_code, _USER_MESSAGES_TR[ErrorCode.UNKNOWN]),
        "technical_detail": technical,
    }


def classify_late_response(result: dict, service: str = "late") -> dict:
    """Enrich a Late API error dict with structured error fields.

    Late API methods return ``{"success": False, "error": str,
    "status_code": int}`` instead of raising exceptions. This function
    adds the new structured fields while preserving all original fields.

    Args:
        result: The original Late API error dict.
        service: Service identifier (default ``"late"``).

    Returns:
        Enriched error dict with structured fields.
    """
    status_code = result.get("status_code")
    error_text = result.get("error", "Unknown error")

    if status_code and status_code in _LATE_MAP:
        error_code, retryable, retry_after = _LATE_MAP[status_code]
    else:
        error_code = ErrorCode.UNKNOWN
        retryable = False
        retry_after = None

    return {
        # Preserve all original fields
        **result,
        # Add structured fields
        "error_code": error_code,
        "service": service,
        "retryable": retryable,
        "retry_after_seconds": retry_after,
        "user_message_tr": _USER_MESSAGES_TR.get(error_code, _USER_MESSAGES_TR[ErrorCode.UNKNOWN]),
        "technical_detail": f"HTTP {status_code}: {error_text}" if status_code else error_text,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_by_class_name(exc: Exception) -> tuple[ErrorCode, bool, int | None] | None:
    """Classify by exception class name (for google.api_core.exceptions)."""
    class_name = type(exc).__name__
    if class_name in _FIREBASE_MAP:
        return _FIREBASE_MAP[class_name]
    # Walk MRO for subclass matches
    for cls in type(exc).__mro__:
        if cls.__name__ in _FIREBASE_MAP:
            return _FIREBASE_MAP[cls.__name__]
    return None


def _fallback_by_status(code: int) -> tuple[ErrorCode, bool, int | None]:
    """Generic fallback classification by HTTP status code range."""
    if code == 429:
        return ErrorCode.RATE_LIMIT, True, 60
    elif 400 <= code < 500:
        return ErrorCode.INVALID_INPUT, False, None
    elif 500 <= code < 600:
        return ErrorCode.SERVER_ERROR, True, 30
    return ErrorCode.UNKNOWN, False, None
