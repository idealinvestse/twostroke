"""Procedural texture generation for materials."""

import math
import random
import pygame
from typing import Tuple


def generate_brushed_metal(size: Tuple[int, int], color: Tuple[int, int, int], 
                           density: float = 0.5) -> pygame.Surface:
    """Generate brushed metal texture with directional lines.
    
    Args:
        size: (width, height) of texture
        color: Base color (R, G, B)
        density: Line density (0.0-1.0)
        
    Returns:
        Surface with brushed metal texture
    """
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((*color, 255))
    
    # Draw horizontal brush lines
    num_lines = int(height * density * 2)
    for i in range(num_lines):
        y = random.randint(0, height - 1)
        line_color = (
            max(0, color[0] + random.randint(-20, 20)),
            max(0, color[1] + random.randint(-20, 20)),
            max(0, color[2] + random.randint(-20, 20)),
            random.randint(100, 180)
        )
        length = random.randint(20, width)
        x_start = random.randint(0, width - length)
        pygame.draw.line(surface, line_color, (x_start, y), (x_start + length, y), 1)
    
    return surface


def generate_noise_texture(size: Tuple[int, int], scale: float = 1.0) -> pygame.Surface:
    """Generate noise texture for surface variation.
    
    Args:
        size: (width, height) of texture
        scale: Noise scale (higher = finer detail)
        
    Returns:
        Surface with noise pattern
    """
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((128, 128, 128, 255))
    
    # Simple value noise
    for x in range(0, width, max(1, int(2 / scale))):
        for y in range(0, height, max(1, int(2 / scale))):
            value = random.randint(-30, 30)
            color = (128 + value, 128 + value, 128 + value, 255)
            rect_size = max(1, int(2 / scale))
            pygame.draw.rect(surface, color, (x, y, rect_size, rect_size))
    
    return surface


def generate_wear_marks(size: Tuple[int, int], intensity: float = 0.3) -> pygame.Surface:
    """Generate wear/heat marks texture.
    
    Args:
        size: (width, height) of texture
        intensity: Mark intensity (0.0-1.0)
        
    Returns:
        Surface with wear marks (alpha channel only)
    """
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    
    num_marks = int(20 * intensity)
    for i in range(num_marks):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        radius = random.randint(5, 30)
        alpha = int(random.randint(30, 100) * intensity)
        
        # Gradient circle
        for r in range(radius, 0, -2):
            a = int(alpha * (r / radius))
            color = (50, 40, 30, a)
            pygame.draw.circle(surface, color, (x, y), r, 1)
    
    return surface


def generate_oil_stains(size: Tuple[int, int], count: int = 5) -> pygame.Surface:
    """Generate oil/fuel stain texture.
    
    Args:
        size: (width, height) of texture
        count: Number of stains
        
    Returns:
        Surface with oil stains (dark, semi-transparent)
    """
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    
    for i in range(count):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        radius = random.randint(10, 40)
        
        # Irregular stain shape
        points = []
        for angle in range(0, 360, 30):
            r = radius * random.uniform(0.7, 1.3)
            px = x + r * math.cos(math.radians(angle))
            py = y + r * math.sin(math.radians(angle))
            points.append((px, py))
        
        color = (20, 20, 25, random.randint(40, 80))
        if len(points) >= 3:
            pygame.draw.polygon(surface, color, points)
    
    return surface


def combine_textures(base: pygame.Surface, *overlays: pygame.Surface, 
                    blend_mode: int = pygame.BLEND_RGBA_MULT) -> pygame.Surface:
    """Combine multiple texture layers.
    
    Args:
        base: Base texture
        overlays: Texture layers to overlay
        blend_mode: PyGame blend mode
        
    Returns:
        Combined texture surface
    """
    result = base.copy()
    for overlay in overlays:
        result.blit(overlay, (0, 0), special_flags=blend_mode)
    return result


def generate_material_texture(material_type: str, size: Tuple[int, int]) -> pygame.Surface:
    """Generate complete material texture based on type.
    
    Args:
        material_type: 'cylinder', 'crankcase', 'piston', 'conrod', 'intake', 'exhaust'
        size: (width, height) of texture
        
    Returns:
        Complete material texture
    """
    if material_type == 'cylinder':
        # Brushed aluminum with heat marks
        base = generate_brushed_metal(size, (180, 180, 190), 0.6)
        wear = generate_wear_marks(size, 0.4)
        return combine_textures(base, wear, blend_mode=pygame.BLEND_RGBA_MULT)
    
    elif material_type == 'crankcase':
        # Cast aluminum with oil stains
        base = generate_noise_texture(size, 2.0)
        # Tint to aluminum color
        tint = pygame.Surface(size, pygame.SRCALPHA)
        tint.fill((170, 175, 180, 200))
        oil = generate_oil_stains(size, 8)
        return combine_textures(base, tint, oil, blend_mode=pygame.BLEND_RGBA_MULT)
    
    elif material_type == 'piston':
        # Machined aluminum, very clean
        base = generate_brushed_metal(size, (200, 200, 205), 0.8)
        return base
    
    elif material_type == 'conrod':
        # Steel with machining marks
        base = generate_brushed_metal(size, (140, 145, 150), 0.5)
        # Darken slightly for steel
        tint = pygame.Surface(size, pygame.SRCALPHA)
        tint.fill((140, 145, 150, 180))
        return combine_textures(base, tint, blend_mode=pygame.BLEND_RGBA_MULT)
    
    elif material_type == 'intake':
        # Plastic/rubber intake
        base = pygame.Surface(size, pygame.SRCALPHA)
        base.fill((80, 90, 100, 255))
        texture = generate_noise_texture(size, 3.0)
        return combine_textures(base, texture, blend_mode=pygame.BLEND_RGBA_MULT)
    
    elif material_type == 'exhaust':
        # Steel with heat discoloration
        base = generate_brushed_metal(size, (100, 100, 110), 0.4)
        # Heat marks (blue/purple tint)
        heat = generate_wear_marks(size, 0.6)
        heat_tint = pygame.Surface(size, pygame.SRCALPHA)
        heat_tint.fill((80, 70, 100, 50))
        return combine_textures(base, heat, heat_tint, blend_mode=pygame.BLEND_RGBA_MULT)
    
    else:
        # Default gray
        return pygame.Surface(size)
        pygame.Surface(size).fill((128, 128, 128, 255))
