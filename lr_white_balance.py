"""Shared white-balance adjustment relative to the camera-rendered base image."""
import math


def _kelvin_rgb(kelvin: float):
    t = max(1000.0, min(40000.0, float(kelvin))) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    return tuple(max(0.01, min(255.0, v)) / 255.0 for v in (r, g, b))


def white_balance_gains(temp_delta_k: float, tint: float):
    """Return RGB gains; adjustments are relative to the already-applied camera WB."""
    base = _kelvin_rgb(6500.0)
    target = _kelvin_rgb(6500.0 + float(temp_delta_k))
    gains = [target[i] / base[i] for i in range(3)]
    # Positive tint moves toward magenta; negative tint moves toward green.
    green_gain = 1.0 - max(-100.0, min(100.0, float(tint))) * 0.003
    gains[1] *= green_gain
    # Normalize exposure so the adjustment primarily changes color, not brightness.
    norm = (gains[0] * gains[1] * gains[2]) ** (1.0 / 3.0)
    return tuple(g / norm for g in gains)
