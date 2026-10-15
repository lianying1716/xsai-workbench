#!/usr/bin/env python3
"""生成星采官网使用的原创背景插画。

调用本机 ComfyUI（Qwen-Image 2.1）出图，写入 site/assets/art/。
用法：python3 tools/gen_art.py [名字 ...]   # 不传则生成全部
"""

from __future__ import annotations

import json
import random
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:18189"
WORKFLOW = Path("/path/to/local-llm/runtime/qwen-image-2.1-workflow.json")
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "art"

NEGATIVE = (
    "text, letters, words, typography, captions, labels, numbers, watermark, signature, logo, "
    "ui screenshot, blurry, low quality, jpeg artifacts, cluttered"
)

STYLE = (
    "flat vector editorial illustration, bold geometric Bauhaus shapes, "
    "hard edges, thick outlines, limited palette of warm cream #f6f2e9, brick red #c1352b, "
    "cobalt blue #1f4fd8, mustard yellow #efb61c, deep navy #17161a, "
    "screen-print poster texture, generous negative space, no gradients"
)

ASSETS: dict[str, dict] = {
    "orbit-knowledge": {
        "size": (1344, 768),
        "prompt": (
            "Abstract knowledge constellation: dozens of small rounded video-card rectangles "
            "drift along wide sweeping orbital rings, spiralling inward toward one large "
            "eight-pointed star at the right side. Thin concentric orbit lines, a few tiny "
            "planet dots. Left two thirds stay calm and mostly empty for text overlay. "
            + STYLE
        ),
    },
    "scattered-saves": {
        "size": (1344, 768),
        "prompt": (
            "Editorial metaphor of lost saved videos: several open rectangular video cards "
            "tumble and scatter apart across the canvas, some fading into small dust specks, "
            "while a neat stack of aligned cards sits intact at the lower left. Empty upper "
            "right area for text. " + STYLE
        ),
    },
    "local-server": {
        "size": (1344, 768),
        "prompt": (
            "Private deployment metaphor: a sturdy geometric server tower on the left with "
            "thick outline, connected by a short bold cable to a large closed padlock and a "
            "sealed archive box on the right. Concentric shield rings radiate outward. Calm "
            "empty space along the top and center. " + STYLE
        ),
    },
    "media-wall": {
        "size": (1344, 768),
        "prompt": (
            "A neatly organised wall of media cards: six rounded rectangular video cards in a "
            "clean grid, each card holding a simple abstract thumbnail shape and three short "
            "text bars underneath, connected by thin lines to a compact text document panel on "
            "the right. Everything aligned to a strict grid, generous margins. " + STYLE
        ),
    },
    "pipeline-stages": {
        "size": (1344, 768),
        "prompt": (
            "A horizontal four stage process illustration: a stack of video card rectangles, "
            "then a downward arrow into a mechanical gear, then a smooth audio waveform bar, "
            "then an open text document, all linked by thick arrows on one baseline. Flat "
            "diagram style, evenly spaced, minimal detail. " + STYLE
        ),
    },
}


def build(name: str, spec: dict) -> dict:
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    w, h = spec["size"]
    wf["4"]["inputs"]["prompt"] = spec["prompt"]
    wf["4"]["inputs"]["negative_prompt"] = NEGATIVE
    wf["8"]["inputs"]["width"] = w
    wf["8"]["inputs"]["height"] = h
    wf["5"]["inputs"]["seed"] = random.randrange(1, 2**31)
    wf["5"]["inputs"]["steps"] = 30
    wf["7"]["inputs"]["filename_prefix"] = f"stargather/{name}"
    return wf


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        COMFY + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get(path: str) -> bytes:
    with urllib.request.urlopen(COMFY + path, timeout=120) as resp:
        return resp.read()


def run(name: str) -> None:
    spec = ASSETS[name]
    job = post("/prompt", {"prompt": build(name, spec), "client_id": "stargather-site"})
    job_id = job["prompt_id"]
    print(f"[{name}] queued {job_id}", flush=True)

    deadline = time.time() + 900
    while time.time() < deadline:
        hist = json.loads(get(f"/history/{job_id}"))
        if job_id in hist:
            outputs = hist[job_id].get("outputs", {})
            for node in outputs.values():
                for img in node.get("images", []):
                    data = get(
                        "/view?" + urllib.parse.urlencode(
                            {"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")}
                        )
                    )
                    OUT_DIR.mkdir(parents=True, exist_ok=True)
                    dest = OUT_DIR / f"{name}.png"
                    dest.write_bytes(data)
                    print(f"[{name}] saved {dest} ({len(data)} bytes)", flush=True)
                    return
            raise RuntimeError(f"{name}: prompt finished with no images: {hist[job_id]}")
        time.sleep(3)
    raise TimeoutError(f"{name}: timed out")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used by run)

    wanted = sys.argv[1:] or list(ASSETS)
    for key in wanted:
        run(key)
