"""URL validation to prevent SSRF attacks."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


_DNS_TIMEOUT_S = 3.0


def validate_url_not_private(url: str) -> bool:
    """Returns True if URL points to a public IP, False if private/internal."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        # Block obvious internal hostnames
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"):
            return False
        if hostname.endswith(".internal") or hostname.endswith(".local"):
            return False
        # Resolve with timeout to prevent hanging on slow DNS
        socket.setdefaulttimeout(_DNS_TIMEOUT_S)
        try:
            ip = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)[0][4][0]
        finally:
            socket.setdefaulttimeout(None)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False
        return True
    except Exception:
        return False
