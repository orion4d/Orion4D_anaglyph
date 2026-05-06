# ============================================================================
# __init__.py
# Orion4D Anaglyph - ComfyUI custom node package
# ============================================================================

from .orion4d_anaglyph import (
    NODE_CLASS_MAPPINGS as _ANAGLYPH_CLASS,
    NODE_DISPLAY_NAME_MAPPINGS as _ANAGLYPH_DISPLAY,
)

from .preset_manager import register_routes


NODE_CLASS_MAPPINGS = {
    **_ANAGLYPH_CLASS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **_ANAGLYPH_DISPLAY,
}

WEB_DIRECTORY = "./web"

register_routes()

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
