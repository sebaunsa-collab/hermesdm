"""
dm/image_generator.py — Generador de imágenes de escena para HermesDM.

Usa Pollinations.ai (gratis, rápido, sin API key) para generar imágenes de escenas D&D.
El endpoint público es https://image.pollinations.ai/

Uso:
    from dm.image_generator import generate_scene_image

    # Imagen gratuita (Pollinations público)
    path = generate_scene_image(narrative="El dragón aparece sobre el castillo")
    # path = "/tmp/hermesdm/scene_abc123.png"
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Ruta base para imágenes cacheadas — configurable via HERMESDM_DATA_DIR
_DATA_DIR = os.environ.get("HERMESDM_DATA_DIR", "~/.hermes/hermesdm")
IMAGE_CACHE_DIR = Path(_DATA_DIR).expanduser() / "generated_images"


def _ensure_cache_dir() -> Path:
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return IMAGE_CACHE_DIR


def generate_scene_image(
    narrative: str,
    output_path: str | None = None,
    timeout: int = 30,
) -> str | None:
    """
    Genera una imagen para una escena D&D via Pollinations.ai.

    Usa el endpoint público gratuito — no requiere API key.

    Args:
        narrative: Texto narrativo de la escena
        output_path: Ruta de salida (None = auto desde hash)
        timeout: Segundos máximos de espera

    Returns:
        Ruta de la imagen generada, o None si falla
    """
    # Buscar image_from_scene.py junto a este archivo, o en scripts/
    _scripts_dir = Path(__file__).parent.parent / "scripts"
    _fallback_script = Path("/usr/local/bin/image_from_scene.py")
    script = _scripts_dir / "image_from_scene.py"

    # Usar sys.executable en vez de path hardcodeado al venv
    python_bin = sys.executable

    if not script.exists() and not _fallback_script.exists():
        print(f"[image_generator] image_from_scene.py not found (tried {script} and {_fallback_script})")
        return None

    actual_script = str(script if script.exists() else _fallback_script)

    # Generar path desde hash del narrative
    _ensure_cache_dir()
    if output_path is None:
        img_hash = abs(hash(narrative)) % 999999
        output_path = str(IMAGE_CACHE_DIR / f"scene_{img_hash}.png")

    try:
        result = subprocess.run(
            [python_bin, actual_script, narrative, "--output", output_path, "--timeout", str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        else:
            print(f"[image_generator] Pollinations failed: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("[image_generator] Pollinations timeout")
        return None
    except Exception as e:
        print(f"[image_generator] error: {e}")
        return None
