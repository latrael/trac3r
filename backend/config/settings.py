from __future__ import annotations

import os


def get_supabase_url() -> str:
    value = os.getenv("SUPABASE_URL", "").strip()
    if not value:
        raise RuntimeError("SUPABASE_URL is required.")
    return value


def get_supabase_service_role_key() -> str:
    value = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not value:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required.")
    return value
