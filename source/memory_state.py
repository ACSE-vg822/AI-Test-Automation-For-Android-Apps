from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MemoryState:
    """Global memory state for automation execution"""
    current_plan: Optional[List] = None
    current_step_index: int = 0
    failed_nav_fallbacks: int = 0
    current_user_request: Optional[str] = None
    current_app_context_file: Optional[str] = None
    current_ui_elements: Optional[List] = None
    current_use_ui_elements: bool = True

# Global memory state instance
memory_state = MemoryState() 