from __future__ import annotations

# Thin alias so callers can import a stable router name
# and include it as receipts_index_router without changing
# existing paths or behavior.
from apps.gateway.transform_receipts import router as router  # re-export
