# ============================================================================
# preset_manager.py
# Orion4D Anaglyph preset backend
## ============================================================================

import json
import re
from pathlib import Path

from aiohttp import web
from server import PromptServer


PACKAGE_DIR = Path(__file__).resolve().parent
PRESETS_DIR = PACKAGE_DIR / "presets"

NODE_NAME = "Orion4D_DepthAnaglyph"
ROUTE_BASE = "/orion4d/anaglyph"

DEFAULT_PRESET_VALUES = {
    "strength": 24.0,
    "convergence": 0.50,
    "shift_mode": "symmetric",
    "depth_invert": False,
    "depth_blur": 3,
    "depth_gamma": 1.0,
    "depth_contrast": 1.0,
    "near_clip": 0.0,
    "far_clip": 1.0,
    "anaglyph_mode": "optimized_dubois_red_cyan",
    "sbs_layout": "left_right",
    "swap_eyes": False,
    "padding_mode": "border",
    "interpolation": "bilinear",
}


def ensure_dirs():
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_preset_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Preset name must be a string.")

    name = name.strip()
    name = re.sub(r"[^a-zA-Z0-9_\- ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    if not name:
        raise ValueError("Preset name is empty.")

    if len(name) > 80:
        name = name[:80].strip()

    if not name:
        raise ValueError("Preset name invalid.")

    return name


def preset_file_path(name: str) -> Path:
    return PRESETS_DIR / f"{sanitize_preset_name(name)}.json"


def safe_json_load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict):
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def make_preset_payload(name: str, values: dict):
    return {
        "name": name,
        "version": 2,
        "node": NODE_NAME,
        "values": values,
    }


def iter_presets():
    ensure_dirs()
    presets = {}

    for path in sorted(PRESETS_DIR.glob("*.json")):
        data = safe_json_load(path)
        if not data:
            continue

        name = data.get("name") or path.stem
        values = data.get("values", {})

        if not isinstance(values, dict):
            continue

        presets[name] = {
            "name": name,
            "file": path.name,
            "values": values,
        }

    return presets


async def list_presets(request):
    presets = iter_presets()

    items = [
        {
            "name": preset["name"],
            "file": preset["file"],
        }
        for _, preset in sorted(presets.items(), key=lambda kv: kv[0].lower())
    ]

    return web.json_response(
        {
            "ok": True,
            "presets": items,
            "folder": str(PRESETS_DIR),
        }
    )


async def get_preset(request):
    name = request.match_info.get("name", "")

    try:
        name = sanitize_preset_name(name)
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    presets = iter_presets()

    if name not in presets:
        return web.json_response({"ok": False, "error": "Preset not found."}, status=404)

    return web.json_response({"ok": True, "preset": presets[name]})


async def get_defaults(request):
    return web.json_response(
        {
            "ok": True,
            "node": NODE_NAME,
            "defaults": DEFAULT_PRESET_VALUES,
        }
    )


async def save_preset(request):
    try:
        payload = await request.json()
        name = sanitize_preset_name(payload.get("name", ""))
        values = payload.get("values", {})

        if not isinstance(values, dict):
            raise ValueError("Field 'values' must be a dict.")

    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    ensure_dirs()

    path = preset_file_path(name)
    data = make_preset_payload(name, values)
    write_json(path, data)

    return web.json_response(
        {
            "ok": True,
            "message": "Preset saved.",
            "preset": {
                "name": name,
                "file": path.name,
                "values": values,
            },
        }
    )


async def delete_preset(request):
    try:
        payload = await request.json()
        name = sanitize_preset_name(payload.get("name", ""))

    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    path = preset_file_path(name)

    if not path.exists():
        return web.json_response({"ok": False, "error": "Preset not found."}, status=404)

    path.unlink(missing_ok=True)

    return web.json_response(
        {
            "ok": True,
            "message": "Preset deleted.",
            "name": name,
        }
    )


def register_routes():
    ensure_dirs()
    routes = PromptServer.instance.routes

    routes.get(f"{ROUTE_BASE}/presets")(list_presets)
    routes.get(f"{ROUTE_BASE}/preset/{{name}}")(get_preset)
    routes.get(f"{ROUTE_BASE}/defaults")(get_defaults)
    routes.post(f"{ROUTE_BASE}/save")(save_preset)
    routes.post(f"{ROUTE_BASE}/delete")(delete_preset)
