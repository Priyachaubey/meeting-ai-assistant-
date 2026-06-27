"""slowapi has been listed in requirements.txt since before this audit began, but was never
actually instantiated or applied to a single route — dead-weight dependency, same pattern as
the 936 empty files this whole project started by cleaning up, just smaller. The guest share
link endpoint (routes/guest.py) is the first genuinely public, unauthenticated, brute-
forceable surface in this app, which is exactly what rate limiting is for — so it's wired up
for real now, applied only where there's an actual reason for it, not added everywhere
speculatively.

NOTE: written against slowapi's documented API from training knowledge — not exercised
against a live request (no network access in this sandbox to actually trigger a 429).
Verify `Limiter(key_func=get_remote_address)` + the `@limiter.limit(...)` decorator shape
against the installed version before relying on it.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
