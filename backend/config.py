"""
Configuration settings for SHIM Proxy
"""
import os
from pydantic import BaseModel
from typing import List, Optional

class Settings(BaseModel):
    PROJECT_NAME: str = "SHIM — Adaptive API Compatibility Platform"
    VERSION: str = "0.1.0"
    PROXY_HOST: str = os.getenv("SHIM_PROXY_HOST", "127.0.0.1")
    PROXY_PORT: int = int(os.getenv("SHIM_PROXY_PORT", "8000"))
    DEFAULT_TARGET_URL: str = os.getenv("SHIM_TARGET_URL", "http://127.0.0.1:8001")
    
    # Timeouts in seconds
    CONNECT_TIMEOUT: float = float(os.getenv("SHIM_CONNECT_TIMEOUT", "3.0"))
    READ_TIMEOUT: float = float(os.getenv("SHIM_READ_TIMEOUT", "5.0"))
    WRITE_TIMEOUT: float = float(os.getenv("SHIM_WRITE_TIMEOUT", "5.0"))
    
    # Hop-by-hop headers to strip during forwarding
    HOP_BY_HOP_HEADERS: List[str] = [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length"
    ]
    
    # SSRF Protection: Allowed domains/IPs or strict patterns
    # In development/test mode, localhost and 127.0.0.1 are permitted for mock providers
    ALLOWED_TARGET_SCHEMES: List[str] = ["http", "https"]
    BLOCKED_INTERNAL_CIDRS: List[str] = [
        "169.254.169.254", # AWS/GCP Instance metadata
        "100.100.100.200", # Alibaba metadata
    ]

settings = Settings()
