"""
Security utilities including SSRF prevention and header sanitization.
"""
from urllib.parse import urlparse
from typing import Dict
from config import settings

def is_safe_target_url(url: str) -> bool:
    """
    Validate that an upstream target URL does not attempt SSRF against
    cloud metadata endpoints or disallowed protocol schemes.
    """
    if not url:
        return False
        
    try:
        parsed = urlparse(url)
    except Exception:
        return False
        
    if parsed.scheme.lower() not in settings.ALLOWED_TARGET_SCHEMES:
        return False
        
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
        
    # Block cloud instance metadata IP endpoints
    if hostname in settings.BLOCKED_INTERNAL_CIDRS:
        return False
        
    return True

def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Strip hop-by-hop headers to prevent connection smuggling or header injection.
    """
    cleaned = {}
    for key, value in headers.items():
        if key.lower() not in settings.HOP_BY_HOP_HEADERS:
            cleaned[key] = value
    return cleaned
