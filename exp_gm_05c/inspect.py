from __future__ import annotations

import hashlib

from exp_gm_05b.inspect import (  # noqa: F401
    declared_patch,
    registered_value,
    spec_version,
    unregistered_names,
    values_match,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
