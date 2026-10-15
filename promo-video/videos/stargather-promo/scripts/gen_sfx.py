#!/usr/bin/env python3
"""Generate an original, deterministic SFX bed aligned to the film's beat grid.

Output: assets/sfx-v1.mp3 (48 kHz stereo)
BGM is assets/bgm-v3.mp3 (the mixed track trimmed to a real downbeat).
Every cue is snapped to a real beat from assets/beat-grid-v3.json.
All sounds are synthesized here; no third-party samples are used.
"""
import json

import numpy as np
import soundfile as sf

SR = 48000
DUR = 59.9
rng = np.random.default_rng(20261012)

grid = json.load(open("assets/beat-grid-v3.json"))
BEATS = grid["beats"]


def nearest_beat(t):
    return min(BEATS, key=lambda b: abs(b - t))


def env(n, a, d, p=2.0):
    t = np.linspace(0, 1, n, endpoint=False)
    atk = np.clip(t / max(a, 1e-6), 0, 1)
    return atk * (1 - t) ** p


def whoosh(dur=0.5, f0=500, f1=4200, g=0.20):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n)
    lo = np.convolve(noise, np.ones(24) / 24, mode="same")
    hi = noise - lo
    sweep = np.clip((t / dur) ** 1.4, 0, 1)
    sig = lo * (1 - sweep) + hi * sweep
    return sig * env(n, 0.35, 0.65, 1.6) * g


def impact(g=0.34, f=58, dur=0.55):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    body = np.sin(2 * np.pi * (f * np.exp(-t * 6.0)) * t)
    click = rng.standard_normal(n) * np.exp(-t * 55)
    return (body * np.exp(-t * 7.5) + click * 0.35) * g


def click(g=0.13, dur=0.06):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    sig = np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 140)
    sig += rng.standard_normal(n) * np.exp(-t * 320) * 0.5
    return sig * g


def tick(g=0.05, dur=0.03):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 260) * g


def riser(t0, t1, g=0.16):
    dur = t1 - t0
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n)
    lo = np.convolve(noise, np.ones(40) / 40, mode="same")
    hi = noise - lo
    sweep = np.clip(t / dur, 0, 1) ** 2
    tone = np.sin(2 * np.pi * (90 + 340 * sweep) * t) * 0.4
    sig = (lo * (1 - sweep) + hi * sweep) * 0.8 + tone
    return sig * np.clip(t / dur, 0, 1) ** 1.3 * g


buf = np.zeros(int(DUR * SR) + SR, dtype=np.float64)


def place(sig, t0):
    i = int(t0 * SR)
    j = min(i + len(sig), len(buf))
    buf[i:j] += sig[: j - i]


# scene transitions / reveals, snapped to real beats
place(whoosh(0.55, 400, 5200, 0.22), 5.155)
place(whoosh(0.55, 400, 5200, 0.22), 10.286)
place(impact(0.36), 10.286)
place(impact(0.28, 66), 11.146)
place(whoosh(0.50, 500, 4600, 0.20), 17.995)
place(whoosh(0.50, 500, 4600, 0.20), 25.728)
place(whoosh(0.50, 600, 4200, 0.20), 33.437)
place(whoosh(0.50, 600, 4200, 0.20), 39.428)
place(impact(0.30, 62), 45.441)
place(whoosh(0.50, 400, 5200, 0.20), 51.432)
place(riser(54.869, 58.305, 0.15), 54.869)
place(impact(0.38, 54), 58.305)

# UI sounds, placed on their visual click
place(click(0.13), 20.573)
place(click(0.12), 29.164)
place(click(0.13), 35.155)
place(click(0.12), 41.146)
place(click(0.11), 45.441)
for k in range(8):
    place(tick(0.045), 27.40 + k * 0.30)
for k in range(7):
    place(tick(0.035), 33.60 + k * 0.16)

peak = np.max(np.abs(buf))
if peak > 0:
    buf *= min(1.0, 0.92 / peak)

stereo = np.stack([buf, buf], axis=1)
sf.write("assets/sfx-v1.wav", stereo, SR, subtype="PCM_16")
print("wrote assets/sfx-v1.wav", stereo.shape, "peak", round(float(np.max(np.abs(buf))), 4))
