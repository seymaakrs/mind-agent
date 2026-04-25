"""
URL safety helpers — outbound HTTP isteklerini SSRF saldirilarindan korur.

Saldiri ornegi: scrape_for_seo gibi bir tool, kullanici tarafindan kontrol
edilen URL'ye GET atar. Saldirgan `http://169.254.169.254/...` (cloud
metadata) verirse servis hesabi credential'lari sizar.

Korumalar:
1. Sadece http/https scheme'leri kabul edilir.
2. Hostname mutlaka resolve edilmeli — getaddrinfo basarisiz olursa fail-closed.
3. Resolve edilen TUM IP'ler private/loopback/link-local/reserved kontrolunden
   gecer; biri bile bu kategorideyse istek reddedilir.
4. Redirect saldirisi: redirect zinciri her hop'ta yeniden validate edilir
   (safe_get). Public URL → private URL redirect'i bu sayede tespit edilir.

SECURITY_REPORT_TR.md Madde 1.
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Maksimum redirect zinciri; httpx default'u 20'dir, biz 5 ile sinirliyoruz.
MAX_REDIRECTS: int = 5

REDIRECT_STATUS: frozenset[int] = frozenset({301, 302, 303, 307, 308})


class UnsafeURLError(Exception):
    """URL SSRF/private-network kontrolunu gecemedi."""


def _is_private_or_unsafe_ip(addr_str: str) -> bool:
    """Bir IP adresi private/internal mi? (IPv4 + IPv6)"""
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        # Parse edilemiyor → fail-closed
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_url_safety(url: str) -> None:
    """
    URL'nin disari acik HTTP icin guvenli oldugunu dogrular.

    Raises:
        UnsafeURLError: scheme yanlis, hostname yok, veya hostname private/
            internal IP'ye cozulurse.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"URL scheme must be http or https, got {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise UnsafeURLError(f"URL must have a hostname: {url!r}")

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(
            f"Could not resolve hostname {parsed.hostname!r}: {exc}"
        ) from exc

    for entry in addrinfo:
        # entry: (family, type, proto, canonname, sockaddr)
        # sockaddr[0]: IP string
        ip_str = entry[4][0]
        if _is_private_or_unsafe_ip(ip_str):
            raise UnsafeURLError(
                f"Hostname {parsed.hostname!r} resolves to private/reserved/"
                f"local IP {ip_str}; refusing outbound request."
            )


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """
    Guvenli GET — her redirect hop'unda yeniden validate eder.

    httpx'in built-in follow_redirects=True'su redirect zincirinde private
    bir IP'ye gitse bile istek atar. Bu fonksiyon bunu engeller: redirect
    zincirini manuel takip eder, her hop'tan once validate_url_safety
    cagirir.

    Args:
        client: Hazir httpx.AsyncClient (caller timeout'u burada ayarlar).
        url: Initial URL.
        **kwargs: client.get'e gecilecek diger args (headers, params...).

    Returns:
        httpx.Response (final, redirect zinciri sonrasi).

    Raises:
        UnsafeURLError: herhangi bir hop'ta validate basarisiz, ya da cok
            fazla redirect.
    """
    # follow_redirects'i biz manuel yapiyoruz; client'a gecirmeyelim.
    kwargs.pop("follow_redirects", None)

    current_url = url
    for hop in range(MAX_REDIRECTS + 1):
        validate_url_safety(current_url)
        response = await client.get(
            current_url,
            follow_redirects=False,
            **kwargs,
        )
        if response.status_code not in REDIRECT_STATUS:
            return response

        location = response.headers.get("location")
        if not location:
            return response

        # Relative redirect ise resolve et
        current_url = urljoin(str(response.url), location)

    raise UnsafeURLError(
        f"Too many redirects (>{MAX_REDIRECTS}) starting from {url!r}"
    )


__all__ = [
    "UnsafeURLError",
    "validate_url_safety",
    "safe_get",
    "ALLOWED_SCHEMES",
    "MAX_REDIRECTS",
]
