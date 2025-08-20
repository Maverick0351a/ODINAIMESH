from __future__ import annotations

from fastapi import APIRouter

# Prefer installed package name, fallback to local libs path for uvicorn/dev
try:  # pragma: no cover - import tested indirectly
    from odin_core.odin.sft import CORE_ID, sft_info
except ImportError:  # pragma: no cover
    from libs.odin_core.odin.sft import CORE_ID, sft_info


router = APIRouter()


@router.get("/v1/sft/core")
def get_core_sft():
    return sft_info(CORE_ID)

# Optional alpha SFT info endpoint (if present)
try:  # pragma: no cover
    from libs.odin_core.odin.sft_alpha import sft_info as alpha_sft_info

    @router.get("/v1/sft/alpha")
    def get_alpha_sft():
        return alpha_sft_info()
except Exception:
    pass

# Optional beta SFT info endpoint (if present)
try:  # pragma: no cover
    from libs.odin_core.odin.sft_beta import sft_info as beta_sft_info

    @router.get("/v1/sft/beta")
    def get_beta_sft():
        return beta_sft_info()
except Exception:
    pass

# Optional tools SFT info endpoints (odin.task@v1, openai.tool@v1) if present
try:  # pragma: no cover
    from libs.odin_core.odin.sft_tools import (
        sft_info_odin_task as _sft_info_odin_task,
        sft_info_openai_tool as _sft_info_openai_tool,
    )

    @router.get("/v1/sft/odin.task")
    def get_sft_odin_task():
        return _sft_info_odin_task()

    @router.get("/v1/sft/openai.tool")
    def get_sft_openai_tool():
        return _sft_info_openai_tool()
except Exception:
    pass
