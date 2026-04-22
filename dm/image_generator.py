"""
dm/image_generator.py — Generador de imágenes de escena para HermesDM.

Usa Pollinations.ai (gratis, rápido, sin API key) para generar imágenes de escenas D&D.
El endpoint público es https://gen.pollinations.ai/image/{prompt}

Uso:
    from dm.image_generator import generate_scene_image

    # Imagen gratuita (Pollinations público)
    path = generate_scene_image(narrative="El dragón aparece sobre el castillo")
    # path = "/tmp/hermesdm/scene_abc123.png"
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Ruta base para imágenes cacheadas
IMAGE_CACHE_DIR = Path.home() / ".hermes" / "hermesdm" / "generated_images"


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
    script = "/home/hermes/scripts/image_from_scene.py"
    venv_py = "/home/hermes/hermesdm/venv/bin/python3"

    if not os.path.exists(script):
        print(f"[image_generator] image_from_scene.py not found at {script}")
        return None

    # Generar path desde hash del narrative
    _ensure_cache_dir()
    if output_path is None:
        img_hash = abs(hash(narrative)) % 999999
        output_path = str(IMAGE_CACHE_DIR / f"scene_{img_hash}.png")

    try:
        result = subprocess.run(
            [venv_py, script, narrative, "--output", output_path, "--timeout", str(timeout)],
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
