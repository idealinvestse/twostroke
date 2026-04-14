"""Rendering engine v2.1 - High-quality visual effects system."""

from rendering.bloom import BloomProcessor
from rendering.materials import Material, generate_textures
from rendering.animations import AnimationManager
from rendering.gauges import AnalogGauge, Dashboard, create_default_dashboard

__all__ = [
    'BloomProcessor', 
    'Material', 
    'generate_textures', 
    'AnimationManager',
    'AnalogGauge',
    'Dashboard',
    'create_default_dashboard'
]
