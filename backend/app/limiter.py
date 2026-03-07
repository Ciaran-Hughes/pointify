"""
Shared rate-limiter instance.

Centralised here so tests can reliably disable rate limiting by setting
    limiter.enabled = False
on a single object rather than patching every router that creates its own.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
