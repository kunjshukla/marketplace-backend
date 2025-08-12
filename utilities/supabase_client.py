import logging
from functools import lru_cache
from typing import Optional

from config.settings import settings

try:
    # supabase v2 client
    from supabase import create_client, Client  # type: ignore
except Exception:  # pragma: no cover
    create_client = None  # type: ignore
    Client = object  # type: ignore

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_supabase() -> Optional["Client"]:
    """Return a cached Supabase client if configured, else None.
    Prefers service role key (server-side) and falls back to anon key.
    """
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not url or not key or create_client is None:
        return None
    try:
        client: Client = create_client(url, key)  # type: ignore
        return client
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to initialize Supabase client: {e}")
        return None
