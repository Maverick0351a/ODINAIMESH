from __future__ import annotations
"""
Alias module for SFT ontologies/validators.
Exports IDs and validators for odin.task@v1 and openai.tool@v1.
"""
from typing import Any, Dict, Tuple, List

from .sft_tools import (
    ODIN_TASK_ID,
    OPENAI_TOOL_ID,
    sft_info_odin_task,
    sft_info_openai_tool,
    validate_odin_task,
    validate_openai_tool,
)

__all__ = [
    "ODIN_TASK_ID",
    "OPENAI_TOOL_ID",
    "sft_info_odin_task",
    "sft_info_openai_tool",
    "validate_odin_task",
    "validate_openai_tool",
]
