"""Tests for the structured error classification system (src/infra/errors.py)."""
from __future__ import annotations

import pytest

from src.infra.errors import (
    ServiceError,
    ErrorCode,
    classify_error,
    classify_late_response,
)


# ---------------------------------------------------------------------------
# ServiceError Exception
# ---------------------------------------------------------------------------


class TestServiceError:
    """ServiceError RuntimeError'i extend etmeli ve metadata tasimali."""

    def test_extends_runtime_error(self):
        exc = ServiceError("test", status_code=429, service="google_ai")
        assert isinstance(exc, RuntimeError)

    def test_carries_metadata(self):
        exc = ServiceError("msg", status_code=500, service="kling", error_code_hint="SERVER_ERROR")
        assert exc.status_code == 500
        assert exc.service == "kling"
        assert exc.error_code_hint == "SERVER_ERROR"
        assert str(exc) == "msg"

    def test_caught_by_except_runtime_error(self):
        """Mevcut except RuntimeError bloklari ServiceError'u da yakalar."""
        with pytest.raises(RuntimeError):
            raise ServiceError("test", status_code=400, service="test")

    def test_caught_by_except_exception(self):
        """Mevcut except Exception bloklari ServiceError'u da yakalar."""
        with pytest.raises(Exception):
            raise ServiceError("test", status_code=400, service="test")


# ---------------------------------------------------------------------------
# classify_error — Google AI
# ---------------------------------------------------------------------------


class TestClassifyGoogleAI:
    """Google AI servis hatalari icin siniflandirma."""

    def test_rate_limit_429(self):
        exc = ServiceError("API Error 429: RESOURCE_EXHAUSTED", status_code=429, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True
        assert result["retry_after_seconds"] == 60
        assert result["service"] == "google_ai"
        assert "error" in result  # backward compat string field

    def test_server_error_500(self):
        exc = ServiceError("API Error 500: INTERNAL", status_code=500, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True
        assert result["retry_after_seconds"] == 30

    def test_unavailable_503(self):
        exc = ServiceError("UNAVAILABLE", status_code=503, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True

    def test_deadline_exceeded_504(self):
        exc = ServiceError("DEADLINE_EXCEEDED", status_code=504, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.TIMEOUT
        assert result["retryable"] is True

    def test_invalid_argument_400(self):
        exc = ServiceError("INVALID_ARGUMENT", status_code=400, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.INVALID_INPUT
        assert result["retryable"] is False

    def test_permission_denied_403(self):
        exc = ServiceError("PERMISSION_DENIED", status_code=403, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.PERMISSION_DENIED
        assert result["retryable"] is False

    def test_not_found_404(self):
        exc = ServiceError("NOT_FOUND", status_code=404, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.NOT_FOUND
        assert result["retryable"] is False

    def test_content_policy_hint(self):
        exc = ServiceError("Safety filter", status_code=200, service="google_ai", error_code_hint="CONTENT_POLICY")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.CONTENT_POLICY
        assert result["retryable"] is False


# ---------------------------------------------------------------------------
# classify_error — Kling AI
# ---------------------------------------------------------------------------


class TestClassifyKling:
    """Kling AI servis hatalari icin siniflandirma."""

    def test_auth_error_1000(self):
        exc = ServiceError("Kling API Error code=1000: auth failed", status_code=1000, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.AUTH_ERROR
        assert result["retryable"] is False

    def test_token_expired_1004(self):
        exc = ServiceError("Kling API Error code=1004: token expired", status_code=1004, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.AUTH_ERROR
        assert result["retryable"] is True

    def test_insufficient_balance_1101(self):
        exc = ServiceError("Kling API Error code=1101: insufficient balance", status_code=1101, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.INSUFFICIENT_BALANCE
        assert result["retryable"] is False

    def test_content_safety_1301(self):
        exc = ServiceError("Kling API Error code=1301: content safety", status_code=1301, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.CONTENT_POLICY
        assert result["retryable"] is False

    def test_rate_limit_1302(self):
        exc = ServiceError("Kling API Error code=1302: rate limit", status_code=1302, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True

    def test_concurrency_limit_1303(self):
        exc = ServiceError("Kling API Error code=1303: concurrency limit", status_code=1303, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True

    def test_server_error_5000(self):
        exc = ServiceError("Kling API Error 500: internal", status_code=5000, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True

    def test_server_unavailable_5001(self):
        exc = ServiceError("unavailable", status_code=5001, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True

    def test_server_timeout_5002(self):
        exc = ServiceError("timeout", status_code=5002, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.TIMEOUT
        assert result["retryable"] is True

    def test_invalid_param_1200(self):
        exc = ServiceError("invalid param", status_code=1200, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.INVALID_INPUT
        assert result["retryable"] is False

    def test_account_suspended_1100(self):
        exc = ServiceError("account anomaly", status_code=1100, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.AUTH_ERROR
        assert result["retryable"] is False

    def test_resource_expired_1102(self):
        exc = ServiceError("resource expired", status_code=1102, service="kling")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.INSUFFICIENT_BALANCE
        assert result["retryable"] is False


# ---------------------------------------------------------------------------
# classify_error — Late API (dict-based)
# ---------------------------------------------------------------------------


class TestClassifyLate:
    """Late API hatalari icin siniflandirma (dict input)."""

    def test_rate_limit_429(self):
        resp = {"success": False, "error": "Too many requests", "status_code": 429}
        result = classify_late_response(resp, "late")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True
        assert result["service"] == "late"

    def test_auth_error_401(self):
        resp = {"success": False, "error": "Unauthorized", "status_code": 401}
        result = classify_late_response(resp, "late")
        assert result["error_code"] == ErrorCode.AUTH_ERROR
        assert result["retryable"] is False

    def test_forbidden_403(self):
        resp = {"success": False, "error": "Forbidden", "status_code": 403}
        result = classify_late_response(resp, "late")
        assert result["error_code"] == ErrorCode.PERMISSION_DENIED
        assert result["retryable"] is False

    def test_bad_request_400(self):
        resp = {"success": False, "error": "Bad Request", "status_code": 400}
        result = classify_late_response(resp, "late")
        assert result["error_code"] == ErrorCode.INVALID_INPUT
        assert result["retryable"] is False

    def test_not_found_404(self):
        resp = {"success": False, "error": "Not Found", "status_code": 404}
        result = classify_late_response(resp, "late")
        assert result["error_code"] == ErrorCode.NOT_FOUND
        assert result["retryable"] is False

    def test_server_error_500(self):
        resp = {"success": False, "error": "Internal Server Error", "status_code": 500}
        result = classify_late_response(resp, "late")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True

    def test_preserves_original_error_field(self):
        resp = {"success": False, "error": "Original error text", "status_code": 500}
        result = classify_late_response(resp, "late")
        assert result["error"] == "Original error text"
        assert result["success"] is False


# ---------------------------------------------------------------------------
# classify_error — Firebase (google.api_core exceptions)
# ---------------------------------------------------------------------------


class TestClassifyFirebase:
    """Firebase/Google Cloud exception'lari icin siniflandirma."""

    def test_resource_exhausted(self):
        exc = _make_google_exception("ResourceExhausted", 429)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True

    def test_service_unavailable(self):
        exc = _make_google_exception("ServiceUnavailable", 503)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True

    def test_not_found(self):
        exc = _make_google_exception("NotFound", 404)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.NOT_FOUND
        assert result["retryable"] is False

    def test_permission_denied(self):
        exc = _make_google_exception("PermissionDenied", 403)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.PERMISSION_DENIED
        assert result["retryable"] is False

    def test_deadline_exceeded(self):
        exc = _make_google_exception("DeadlineExceeded", 504)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.TIMEOUT
        assert result["retryable"] is True

    def test_invalid_argument(self):
        exc = _make_google_exception("InvalidArgument", 400)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.INVALID_INPUT
        assert result["retryable"] is False

    def test_already_exists(self):
        exc = _make_google_exception("AlreadyExists", 409)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.INVALID_INPUT
        assert result["retryable"] is False

    def test_internal_server_error(self):
        exc = _make_google_exception("InternalServerError", 500)
        result = classify_error(exc, "firebase")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True


# ---------------------------------------------------------------------------
# classify_error — fal.ai
# ---------------------------------------------------------------------------


class TestClassifyFalAI:
    """fal.ai hatalari icin siniflandirma."""

    def test_server_error_503(self):
        exc = ServiceError("runner_scheduling_failure", status_code=503, service="fal_ai")
        result = classify_error(exc, "fal_ai")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True

    def test_timeout_504(self):
        exc = ServiceError("generation_timeout", status_code=504, service="fal_ai")
        result = classify_error(exc, "fal_ai")
        assert result["error_code"] == ErrorCode.TIMEOUT
        assert result["retryable"] is True

    def test_content_policy_422(self):
        exc = ServiceError("content_policy_violation", status_code=422, service="fal_ai")
        result = classify_error(exc, "fal_ai")
        assert result["error_code"] == ErrorCode.CONTENT_POLICY
        assert result["retryable"] is False

    def test_server_error_500(self):
        exc = ServiceError("internal_server_error", status_code=500, service="fal_ai")
        result = classify_error(exc, "fal_ai")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True


# ---------------------------------------------------------------------------
# classify_error — Serper
# ---------------------------------------------------------------------------


class TestClassifySerper:
    """Serper.dev hatalari icin siniflandirma."""

    def test_auth_error_401(self):
        exc = ServiceError("Invalid API key", status_code=401, service="serper")
        result = classify_error(exc, "serper")
        assert result["error_code"] == ErrorCode.AUTH_ERROR
        assert result["retryable"] is False

    def test_rate_limit_429(self):
        exc = ServiceError("Rate limit exceeded", status_code=429, service="serper")
        result = classify_error(exc, "serper")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True

    def test_server_error_500(self):
        exc = ServiceError("Internal Server Error", status_code=500, service="serper")
        result = classify_error(exc, "serper")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True


# ---------------------------------------------------------------------------
# classify_error — Fallback / Edge Cases
# ---------------------------------------------------------------------------


class TestClassifyFallback:
    """Fallback ve edge case siniflandirmalari."""

    def test_timeout_error_type(self):
        exc = TimeoutError("Connection timed out")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.TIMEOUT
        assert result["retryable"] is True

    def test_connection_error(self):
        exc = ConnectionError("Connection refused")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.NETWORK_ERROR
        assert result["retryable"] is True

    def test_plain_runtime_error_with_status_in_message(self):
        """Legacy RuntimeError'dan regex ile status code cikarilir."""
        exc = RuntimeError("API Error 429: Rate limit exceeded")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True

    def test_plain_runtime_error_with_kling_code_in_message(self):
        exc = RuntimeError("Kling API Error code=1101: insufficient balance")
        result = classify_error(exc, "kling")
        assert result["error_code"] == ErrorCode.INSUFFICIENT_BALANCE
        assert result["retryable"] is False

    def test_unknown_exception(self):
        exc = ValueError("Something unexpected")
        result = classify_error(exc, "google_ai")
        assert result["error_code"] == ErrorCode.UNKNOWN
        assert result["retryable"] is False

    def test_result_always_has_backward_compat_fields(self):
        exc = RuntimeError("test error")
        result = classify_error(exc, "google_ai")
        assert "success" in result
        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_result_always_has_structured_fields(self):
        exc = ServiceError("test", status_code=500, service="google_ai")
        result = classify_error(exc, "google_ai")
        required = {"success", "error", "error_code", "service", "retryable",
                     "retry_after_seconds", "user_message_tr", "technical_detail"}
        assert required.issubset(result.keys())

    def test_user_message_tr_is_turkish(self):
        """Her error code icin Turkce kullanici mesaji olmali."""
        exc = ServiceError("test", status_code=429, service="google_ai")
        result = classify_error(exc, "google_ai")
        assert result["user_message_tr"]
        assert isinstance(result["user_message_tr"], str)
        assert len(result["user_message_tr"]) > 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_google_exception(class_name: str, code: int) -> Exception:
    """google.api_core.exceptions simule eden fake exception olusturur."""
    # Dinamik class olustur — __class__ assignment yerine direkt instance uret
    cls = type(class_name, (Exception,), {"__module__": "google.api_core.exceptions"})
    exc = cls(f"{class_name}: test error")
    exc.code = code
    return exc
