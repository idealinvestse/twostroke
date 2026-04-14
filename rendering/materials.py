"""Material system with procedural texture generation and rendering properties."""

import math
from dataclasses import dataclass
from typing import Tuple, Dict
import pygame
from rendering.procedural import generate_material_texture


@dataclass
class Material:
    """Material definition for rendering with PBR-like properties.
    
    Simplified for PyGame 2D rendering but conceptually similar to PBR.
    """
    base_color: Tuple[int, int, int]
    roughness: float  # 0.0 = mirror-like, 1.0 = matte
    metallic: float   # 0.0 = dielectric, 1.0 = metal
    emissive: Tuple[int, int, int] = (0, 0, 0)
    texture_scale: float = 1.0
    
    def get_specular(self, view_angle: float = 0.0) -> Tuple[int, int, int]:
        """Calculate specular highlight color based on material properties.
        
        Args:
            view_angle: Angle from surface normal (radians)
            
        Returns:
            Specular color (R, G, B)
        """
        if self.metallic < 0.1:
            return (0, 0, 0)
        
        # Fresnel-like effect
        fresnel = 1.0 - abs(math.cos(view_angle))
        specular_intensity = self.metallic * (1.0 - self.roughness) * fresnel
        
        return (
            int(self.base_color[0] * specular_intensity),
            int(self.base_color[1] * specular_intensity),
            int(self.base_color[2] * specular_intensity)
        )


class MaterialCache:
    """Cache for generated material textures to avoid regenerating each frame."""
    
    def __init__(self):
        self._cache: Dict[str, pygame.Surface] = {}
        self._texture_size = (256, 256)  # Default texture size
    
    def get_texture(self, material_type: str, size: Tuple[int, int] = None) -> pygame.Surface:
        """Get or generate material texture.
        
        Args:
            material_type: Type identifier ('cylinder', 'crankcase', etc.)
            size: Desired texture size (uses default if None)
            
        Returns:
            Material texture surface
        """
        cache_key = material_type
        if size is not None:
            cache_key = f"{material_type}_{size[0]}x{size[1]}"
        
        if cache_key not in self._cache:
            actual_size = size if size is not None else self._texture_size
            self._cache[cache_key] = generate_material_texture(material_type, actual_size)
        
        return self._cache[cache_key]
    
    def clear(self) -> None:
        """Clear texture cache."""
        self._cache.clear()


# Predefined materials
MATERIALS = {
    'cylinder': Material(
        base_color=(180, 180, 190),
        roughness=0.4,
        metallic=0.9,
        texture_scale=2.0
    ),
    'crankcase': Material(
        base_color=(170, 175, 180),
        roughness=0.6,
        metallic=0.7,
        texture_scale=1.5
    ),
    'piston': Material(
        base_color=(200, 200, 205),
        roughness=0.2,
        metallic=0.95,
        texture_scale=1.0
    ),
    'conrod': Material(
        base_color=(140, 145, 150),
        roughness=0.5,
        metallic=0.8,
        texture_scale=1.0
    ),
    'crankshaft': Material(
        base_color=(130, 135, 140),
        roughness=0.3,
        metallic=0.85,
        texture_scale=1.0
    ),
    'intake': Material(
        base_color=(80, 90, 100),
        roughness=0.9,
        metallic=0.0,
        texture_scale=1.0
    ),
    'exhaust': Material(
        base_color=(100, 100, 110),
        roughness=0.7,
        metallic=0.6,
        texture_scale=1.0,
        emissive=(20, 10, 10)  # Slight heat glow
    ),
    'head': Material(
        base_color=(160, 165, 170),
        roughness=0.3,
        metallic=0.85,
        texture_scale=1.0
    ),
    'spark_plug': Material(
        base_color=(220, 220, 220),
        roughness=0.1,
        metallic=0.9,
        texture_scale=0.5
    ),
    'reed_valve': Material(
        base_color=(180, 180, 180),
        roughness=0.2,
        metallic=0.9,
        texture_scale=1.0
    ),
}


def get_material(name: str) -> Material:
    """Get material definition by name.
    
    Args:
        name: Material identifier
        
    Returns:
        Material definition
    """
    return MATERIALS.get(name, MATERIALS['cylinder'])


def generate_textures(cache: MaterialCache = None) -> Dict[str, pygame.Surface]:
    """Generate all material textures.
    
    Args:
        cache: Optional material cache (creates new if None)
        
    Returns:
        Dictionary mapping material names to texture surfaces
    """
    if cache is None:
        cache = MaterialCache()
    
    textures = {}
    for material_name in MATERIALS.keys():
        textures[material_name] = cache.get_texture(material_name)
    
    return textures
