"""
URL safety helper testleri (SSRF koruma).

validate_url_safety(): scheme + hostname + IP kontrolu.
safe_get(): redirect-aware GET — her hop'ta yeniden validate eder.

SECURITY_REPORT_TR.md Madde 1 (SSRF).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infra.url_safety import (
    UnsafeURLError,
    safe_get,
    validate_url_safety,
)


# ---------------------------------------------------------------------------
# validate_url_safety — scheme + hostname kontrolu
# ---------------------------------------------------------------------------


def _mock_dns(target_ip: str):
    """socket.getaddrinfo mock helper'i — target_ip'yi doner."""
    return patch(
        "socket.getaddrinfo",
        return_value=[(0, 0, 0, "", (target_ip, 0))],
    )


def test_https_public_url_ok():
    with _mock_dns("142.250.74.46"):  # google.com
        validate_url_safety("https://example.com/path")


def test_http_public_url_ok():
    with _mock_dns("93.184.216.34"):  # example.com
        validate_url_safety("http://example.com")


@pytest.mark.parametrize(
    "scheme",
    ["ftp", "file", "gopher", "javascript", "data"],
)
def test_disallowed_scheme_rejected(scheme):
    with pytest.raises(UnsafeURLError, match="scheme"):
        validate_url_safety(f"{scheme}://example.com/x")


def test_no_scheme_rejected():
    with pytest.raises(UnsafeURLError):
        validate_url_safety("example.com")


def test_no_hostname_rejected():
    with pytest.raises(UnsafeURLError, match="hostname"):
        validate_url_safety("http:///path")


# ---------------------------------------------------------------------------
# Private IP red — SSRF asil hedefler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "private_ip",
    [
        "127.0.0.1",         # loopback
        "127.0.0.5",
        "10.0.0.1",          # RFC1918 class A
        "10.255.255.255",
        "172.16.0.1",        # RFC1918 class B
        "172.31.255.255",
        "192.168.0.1",       # RFC1918 class C
        "192.168.1.50",
        "169.254.169.254",   # CLOUD METADATA — kritik hedef
        "169.254.0.1",       # link-local
        "0.0.0.0",           # unspecified
        "224.0.0.1",         # multicast
        "240.0.0.1",         # reserved
    ],
)
def test_private_ipv4_rejected(private_ip):
    with _mock_dns(private_ip):
        with pytest.raises(UnsafeURLError, match="(private|reserved|local)"):
            validate_url_safety("http://attacker.example.com/")


@pytest.mark.parametrize(
    "private_ipv6",
    [
        "::1",               # loopback
        "fe80::1",           # link-local
        "fc00::1",           # unique local
        "fd00::1",
    ],
)
def test_private_ipv6_rejected(private_ipv6):
    with _mock_dns(private_ipv6):
        with pytest.raises(UnsafeURLError):
            validate_url_safety("http://attacker.example.com/")


def test_dns_failure_rejected():
    """DNS resolve edilemezse fail-closed."""
    import socket

    with patch("socket.getaddrinfo", side_effect=socket.gaierror("not found")):
        with pytest.raises(UnsafeURLError, match="resolve"):
            validate_url_safety("http://nonexistent.example/")


def test_multiple_addresses_one_private_rejected():
    """Hostname coklu IP'ye cozulurse, biri bile private ise reddedilir."""
    with patch(
        "socket.getaddrinfo",
        return_value=[
            (0, 0, 0, "", ("8.8.8.8", 0)),
            (0, 0, 0, "", ("127.0.0.1", 0)),  # private!
        ],
    ):
        with pytest.raises(UnsafeURLError):
            validate_url_safety("http://multi.example/")


# ---------------------------------------------------------------------------
# safe_get — redirect-aware GET
# ---------------------------------------------------------------------------


def _fake_response(status_code=200, headers=None, url="http://example.com/"):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.url = url
    return resp


@pytest.mark.asyncio
async def test_safe_get_passes_for_public_url():
    """Mutlu yol: 200 → response donulur."""
    fake_resp = _fake_response(200)
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)

    with _mock_dns("8.8.8.8"):
        result = await safe_get(fake_client, "http://public.example/")

    assert result is fake_resp


@pytest.mark.asyncio
async def test_safe_get_validates_redirect_target():
    """Redirect 169.254.169.254'e gidiyorsa: ikinci hop'ta UnsafeURLError."""
    redirect_resp = _fake_response(
        302,
        headers={"location": "http://169.254.169.254/latest/meta-data/"},
        url="http://attacker.example/",
    )
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=redirect_resp)

    # Ilk hop public, ikinci hop private — DNS mock'i call edildigi sira
    # ile cevap vermeli.
    def dns_side_effect(host, _port, *args, **kwargs):
        if host == "attacker.example":
            return [(0, 0, 0, "", ("8.8.8.8", 0))]
        return [(0, 0, 0, "", ("169.254.169.254", 0))]

    with patch("socket.getaddrinfo", side_effect=dns_side_effect):
        with pytest.raises(UnsafeURLError):
            await safe_get(fake_client, "http://attacker.example/")


@pytest.mark.asyncio
async def test_safe_get_too_many_redirects():
    """Cok fazla redirect → UnsafeURLError."""
    # Her response 302 olur ve baska bir public URL'ye yonlendirir.
    counter = {"i": 0}

    def get_side_effect(*args, **kwargs):
        counter["i"] += 1
        return _fake_response(
            302,
            headers={"location": f"http://hop{counter['i']}.example/"},
            url=f"http://hop{counter['i']}.example/",
        )

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=get_side_effect)

    with _mock_dns("8.8.8.8"):
        with pytest.raises(UnsafeURLError, match="redirects"):
            await safe_get(fake_client, "http://start.example/")


@pytest.mark.asyncio
async def test_safe_get_blocks_private_initial_url():
    """Initial URL private ise hic istek atilmaz."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock()

    with _mock_dns("127.0.0.1"):
        with pytest.raises(UnsafeURLError):
            await safe_get(fake_client, "http://localhost/")

    fake_client.get.assert_not_called()
