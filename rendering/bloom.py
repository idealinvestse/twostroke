"""Bloom post-processing effect using separable Gaussian blur."""

import math
import pygame
from typing import Tuple, Optional


class BloomProcessor:
    """High-quality bloom effect using separable Gaussian blur.
    
    Optimized for real-time rendering with configurable quality levels.
    """
    
    def __init__(self, size: Tuple[int, int], quality: int = 2):
        """Initialize bloom processor.
        
        Args:
            size: (width, height) of the render target
            quality: 1=fast, 2=medium, 3=high quality
        """
        self.width, self.height = size
        self.quality = quality
        self.threshold = 0.7  # Brightness threshold for bloom
        self.intensity = 1.0  # Bloom intensity multiplier
        self.sigma = 4.0  # Blur radius
        self._kernel_cache: dict[tuple[float, int], list[float]] = {}
        
        # Create intermediate surfaces for multi-pass blur
        self._configure_working_size()

    def _downsample_factor(self) -> int:
        """Return the bloom working resolution factor for the selected quality."""
        if self.quality <= 1:
            return 4
        if self.quality == 2:
            return 3
        return 2

    def _configure_working_size(self) -> None:
        """Create intermediate surfaces for the current working resolution."""
        self.work_scale = self._downsample_factor()
        self.work_width = max(1, self.width // self.work_scale)
        self.work_height = max(1, self.height // self.work_scale)
        self._create_surfaces()
        
    def _create_surfaces(self) -> None:
        """Create offscreen surfaces for bloom processing."""
        # Brightness extraction surface
        self.bright_surface = pygame.Surface((self.work_width, self.work_height), pygame.SRCALPHA)
        
        # Horizontal blur surface
        self.blur_h_surface = pygame.Surface((self.work_width, self.work_height), pygame.SRCALPHA)
        
        # Vertical blur surface (final bloom)
        self.blur_v_surface = pygame.Surface((self.work_width, self.work_height), pygame.SRCALPHA)
        
    def set_threshold(self, threshold: float) -> None:
        """Set brightness threshold for bloom extraction."""
        self.threshold = max(0.0, min(1.0, threshold))
        
    def set_intensity(self, intensity: float) -> None:
        """Set bloom intensity multiplier."""
        self.intensity = max(0.0, min(3.0, intensity))
        
    def set_sigma(self, sigma: float) -> None:
        """Set blur radius (sigma)."""
        self.sigma = max(1.0, min(10.0, sigma))
        
    def extract_bright(self, source: pygame.Surface) -> pygame.Surface:
        """Extract bright pixels above threshold."""
        self.bright_surface.fill((0, 0, 0, 0))
        
        # Copy source and threshold on the reduced working buffer
        for x in range(self.work_width):
            for y in range(self.work_height):
                r, g, b, a = source.get_at((x, y))
                luminance = (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
                if luminance > self.threshold:
                    # Boost brightness for bloom
                    boost = (luminance - self.threshold) / (1.0 - self.threshold + 0.001)
                    r = min(255, int(r * boost))
                    g = min(255, int(g * boost))
                    b = min(255, int(b * boost))
                    self.bright_surface.set_at((x, y), (r, g, b, a))
                    
        return self.bright_surface
    
    def gaussian_kernel(self, sigma: float, radius: int) -> list[float]:
        """Generate 1D Gaussian kernel."""
        key = (round(sigma, 6), radius)
        cached = self._kernel_cache.get(key)
        if cached is not None:
            return cached

        kernel = []
        for x in range(-radius, radius + 1):
            weight = math.exp(-(x * x) / (2 * sigma * sigma))
            kernel.append(weight)
        
        # Normalize
        total = sum(kernel)
        kernel = [w / total for w in kernel]
        self._kernel_cache[key] = kernel
        return kernel
    
    def blur_horizontal(self, source: pygame.Surface) -> pygame.Surface:
        """Horizontal Gaussian blur pass."""
        self.blur_h_surface.fill((0, 0, 0, 0))
        kernel = self.gaussian_kernel(self.sigma, int(self.sigma * 2))
        radius = len(kernel) // 2
        
        for y in range(self.work_height):
            for x in range(self.work_width):
                r_sum, g_sum, b_sum, a_sum = 0.0, 0.0, 0.0, 0.0
                
                for kx in range(-radius, radius + 1):
                    src_x = max(0, min(self.work_width - 1, x + kx))
                    r, g, b, a = source.get_at((src_x, y))
                    weight = kernel[kx + radius]
                    r_sum += r * weight
                    g_sum += g * weight
                    b_sum += b * weight
                    a_sum += a * weight
                
                self.blur_h_surface.set_at((x, y), (
                    int(r_sum), int(g_sum), int(b_sum), int(a_sum)
                ))
        
        return self.blur_h_surface
    
    def blur_vertical(self, source: pygame.Surface) -> pygame.Surface:
        """Vertical Gaussian blur pass."""
        self.blur_v_surface.fill((0, 0, 0, 0))
        kernel = self.gaussian_kernel(self.sigma, int(self.sigma * 2))
        radius = len(kernel) // 2
        
        for x in range(self.work_width):
            for y in range(self.work_height):
                r_sum, g_sum, b_sum, a_sum = 0.0, 0.0, 0.0, 0.0
                
                for ky in range(-radius, radius + 1):
                    src_y = max(0, min(self.work_height - 1, y + ky))
                    r, g, b, a = source.get_at((x, src_y))
                    weight = kernel[ky + radius]
                    r_sum += r * weight
                    g_sum += g * weight
                    b_sum += b * weight
                    a_sum += a * weight
                
                self.blur_v_surface.set_at((x, y), (
                    int(r_sum), int(g_sum), int(b_sum), int(a_sum)
                ))
        
        return self.blur_v_surface
    
    def process(self, source: pygame.Surface, target: Optional[pygame.Surface] = None) -> pygame.Surface:
        """Apply full bloom effect to source surface.
        
        Args:
            source: Source surface to apply bloom to
            target: Optional target surface (if None, creates new)
            
        Returns:
            Surface with bloom effect applied
        """
        if self.intensity <= 0.0:
            return source.copy() if target is None else target

        # Downsample before bloom work to reduce the cost of pixel iteration
        working_source = pygame.transform.scale(source, (self.work_width, self.work_height))

        # Extract bright pixels
        bright = self.extract_bright(working_source)
        if bright.get_bounding_rect().width == 0 or bright.get_bounding_rect().height == 0:
            return source.copy() if target is None else target
        
        # Horizontal blur
        blurred_h = self.blur_horizontal(bright)
        
        # Vertical blur
        blurred_v = self.blur_vertical(blurred_h)
        
        # Apply intensity
        if self.intensity != 1.0:
            for x in range(self.work_width):
                for y in range(self.work_height):
                    r, g, b, a = blurred_v.get_at((x, y))
                    r = min(255, int(r * self.intensity))
                    g = min(255, int(g * self.intensity))
                    b = min(255, int(b * self.intensity))
                    blurred_v.set_at((x, y), (r, g, b, a))

        bloom_full = pygame.transform.scale(blurred_v, (self.width, self.height))
        
        # Composite with original using additive blending
        if target is None:
            target = source.copy()
        
        target.blit(bloom_full, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        
        return target
    
    def resize(self, new_size: Tuple[int, int]) -> None:
        """Resize bloom processor to new dimensions."""
        self.width, self.height = new_size
        self._configure_working_size()
