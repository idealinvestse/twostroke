"""Utility functions for physics calculations.
"""

import math
from typing import Tuple


def clamp01(value: float) -> float:
    """Clamp value to [0, 1] range."""
    return max(0.0, min(1.0, value))


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, value))


def rescale_components(*components: float, target_total: float) -> Tuple[float, ...]:
    """Rescale components to sum to target_total while maintaining proportions.
    
    Guards against zero inputs and negative values.
    """
    positive_components = [max(0.0, c) for c in components]
    total = sum(positive_components)
    
    # Guard against zero target_total
    target_total = max(target_total, 1e-12)
    
    if total <= 1e-12:
        # Equal distribution if all components are zero
        share = target_total / max(1, len(positive_components))
        return tuple(share for _ in positive_components)
    
    scale = target_total / total
    return tuple(c * scale for c in positive_components)


def angle_diff(a_deg: float, b_deg: float) -> float:
    """Calculate wrapped angle difference in range [-180, 180].
    
    Args:
        a_deg: First angle in degrees
        b_deg: Second angle in degrees
        
    Returns:
        Wrapped difference (a - b) in range [-180, 180]
    """
    return (a_deg - b_deg + 180.0) % 360.0 - 180.0


def gaussian_falloff(x: float, sigma: float) -> float:
    """Gaussian falloff function: exp(-(x/sigma)²).
    
    Args:
        x: Input value
        sigma: Characteristic width (must be > 0)
        
    Returns:
        Falloff value in range (0, 1]
    """
    sigma = max(sigma, 1e-12)
    return math.exp(-((x / sigma) ** 2))


def is_finite(value: float) -> bool:
    """Check if value is finite (not NaN, not inf)."""
    return math.isfinite(value)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with fallback for zero denominator."""
    if abs(denominator) < 1e-12:
        return default
    return numerator / denominator
