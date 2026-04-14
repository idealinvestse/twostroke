"""Main menu for PyGame 2D engine simulation."""
from typing import Callable, Optional
import pygame

from engine_profiles import list_all_profiles, get_json_profile_metadata
from config import QualityPreset


class MainMenu:
    """Main menu with profile selection, quality preset, and display settings."""
    
    def __init__(self, screen: pygame.Surface, on_start: Callable[[str, QualityPreset], None]):
        """
        Initialize main menu.
        
        Args:
            screen: PyGame surface to render on
            on_start: Callback when user clicks Start. Receives (profile_key, quality_preset)
        """
        self.screen = screen
        self.on_start = on_start
        self.running = True
        
        # Fonts
        self.font_title = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_heading = pygame.font.SysFont("Arial", 24, bold=True)
        self.font_normal = pygame.font.SysFont("Arial", 18)
        self.font_small = pygame.font.SysFont("Arial", 14)
        
        # Colors
        self.bg_color = (15, 15, 25)
        self.panel_color = (30, 30, 40)
        self.panel_border = (60, 60, 80)
        self.text_color = (220, 220, 220)
        self.text_dim = (150, 150, 150)
        self.accent_color = (100, 150, 220)
        self.accent_hover = (120, 170, 240)
        self.button_color = (50, 50, 65)
        self.button_hover = (70, 70, 90)
        self.selected_color = (80, 120, 180)
        
        # Load profiles
        self.profiles = list_all_profiles()  # [(key, name, source), ...]
        self.selected_profile_idx = 0
        
        # Quality presets
        self.quality_presets = [
            QualityPreset.SIMPLE_2D,
            QualityPreset.LOW,
            QualityPreset.MEDIUM,
            QualityPreset.HIGH,
            QualityPreset.ULTRA,
        ]
        self.selected_quality_idx = 0
        
        # Display settings
        self.resolutions = [
            (1280, 720),
            (1366, 768),
            (1600, 900),
            (1920, 1080),
        ]
        self.selected_resolution_idx = 0
        self.fullscreen = False
        
        # Scroll positions
        self.profile_scroll = 0
        self.max_visible_profiles = 8
        
        # UI rects (calculated in draw)
        self.profile_rects: list[tuple[pygame.Rect, int]] = []
        self.quality_rects: list[tuple[pygame.Rect, int]] = []
        self.resolution_rects: list[tuple[pygame.Rect, int]] = []
        self.start_button_rect: Optional[pygame.Rect] = None
        self.fullscreen_rect: Optional[pygame.Rect] = None
        
    def run(self) -> None:
        """Run the menu loop until user starts or quits."""
        clock = pygame.time.Clock()
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    import sys
                    sys.exit()
                self._handle_event(event)
            
            self._draw()
            pygame.display.flip()
            clock.tick(60)
    
    def _handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = event.pos
                
                # Check profile selection
                for rect, idx in self.profile_rects:
                    if rect.collidepoint(mouse_pos):
                        self.selected_profile_idx = idx
                        return
                
                # Check quality selection
                for rect, idx in self.quality_rects:
                    if rect.collidepoint(mouse_pos):
                        self.selected_quality_idx = idx
                        return
                
                # Check resolution selection
                for rect, idx in self.resolution_rects:
                    if rect.collidepoint(mouse_pos):
                        self.selected_resolution_idx = idx
                        return
                
                # Check fullscreen toggle
                if self.fullscreen_rect and self.fullscreen_rect.collidepoint(mouse_pos):
                    self.fullscreen = not self.fullscreen
                    return
                
                # Check start button
                if self.start_button_rect and self.start_button_rect.collidepoint(mouse_pos):
                    self._start_simulation()
        
        elif event.type == pygame.MOUSEWHEEL:
            # Scroll profile list
            if self.profile_rects:
                max_scroll = max(0, len(self.profiles) - self.max_visible_profiles)
                self.profile_scroll = max(0, min(max_scroll, self.profile_scroll - event.y))
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._start_simulation()
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                import sys
                sys.exit()
    
    def _start_simulation(self) -> None:
        """Start the simulation with selected settings."""
        profile_key = self.profiles[self.selected_profile_idx][0]
        quality_preset = self.quality_presets[self.selected_quality_idx]
        
        # Apply display settings
        resolution = self.resolutions[self.selected_resolution_idx]
        self._apply_display_settings(resolution, self.fullscreen)
        
        self.running = False
        self.on_start(profile_key, quality_preset)
    
    def _apply_display_settings(self, resolution: tuple[int, int], fullscreen: bool) -> None:
        """Apply display settings to PyGame."""
        if fullscreen:
            self.screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(resolution)
    
    def _draw(self) -> None:
        """Render the menu."""
        # Validate that we have profiles loaded
        if not self.profiles:
            self.screen.fill((50, 0, 0))
            font = pygame.font.SysFont("Arial", 24)
            text = font.render("Error: No engine profiles loaded!", True, (255, 100, 100))
            rect = text.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
            self.screen.blit(text, rect)
            pygame.display.flip()
            return
        
        self.screen.fill(self.bg_color)
        
        # Title
        title = self.font_title.render("2-Taktsmotor Simulering", True, self.text_color)
        title_rect = title.get_rect(centerx=self.screen.get_width() // 2, top=30)
        self.screen.blit(title, title_rect)
        
        # Layout: Three columns
        col_width = 300
        col_spacing = 40
        start_x = (self.screen.get_width() - (3 * col_width + 2 * col_spacing)) // 2
        y_start = 100
        
        # Column 1: Motor Profile Selection
        self._draw_column(start_x, y_start, col_width, "Motorprofil", self._draw_profile_list)
        
        # Column 2: Quality Preset
        x2 = start_x + col_width + col_spacing
        self._draw_column(x2, y_start, col_width, "Grafikkvalitet", self._draw_quality_list)
        
        # Column 3: Display Settings
        x3 = x2 + col_width + col_spacing
        self._draw_column(x3, y_start, col_width, "Display", self._draw_display_settings)
        
        # Start button at bottom
        self._draw_start_button()
        
        # Profile info panel at bottom
        self._draw_profile_info()
    
    def _draw_column(self, x: int, y: int, width: int, title: str, content_func) -> None:
        """Draw a column with title and content."""
        # Title
        title_surf = self.font_heading.render(title, True, self.text_color)
        self.screen.blit(title_surf, (x, y))
        
        # Panel background
        panel_rect = pygame.Rect(x, y + 35, width, 350)
        pygame.draw.rect(self.screen, self.panel_color, panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.panel_border, panel_rect, width=2, border_radius=8)
        
        # Content
        content_func(x + 10, y + 45, width - 20)
    
    def _draw_profile_list(self, x: int, y: int, width: int) -> None:
        """Draw scrollable profile list."""
        self.profile_rects = []
        item_height = 32
        
        visible_profiles = self.profiles[
            self.profile_scroll:self.profile_scroll + self.max_visible_profiles
        ]
        
        for i, (key, name, source) in enumerate(visible_profiles):
            actual_idx = self.profile_scroll + i
            rect = pygame.Rect(x, y + i * item_height, width, item_height - 2)
            
            # Selection highlight
            is_selected = actual_idx == self.selected_profile_idx
            color = self.selected_color if is_selected else self.button_color
            if is_selected:
                pygame.draw.rect(self.screen, color, rect, border_radius=4)
            
            # Profile name
            text = self.font_normal.render(name, True, self.text_color)
            self.screen.blit(text, (rect.x + 8, rect.y + 6))
            
            self.profile_rects.append((rect, actual_idx))
        
        # Scroll indicator
        if len(self.profiles) > self.max_visible_profiles:
            scroll_text = self.font_small.render(
                f"Scroll: {self.profile_scroll + 1}/{len(self.profiles)}", 
                True, self.text_dim
            )
            self.screen.blit(scroll_text, (x, y + self.max_visible_profiles * item_height + 5))
    
    def _draw_quality_list(self, x: int, y: int, width: int) -> None:
        """Draw quality preset selection."""
        self.quality_rects = []
        item_height = 40
        
        quality_labels = {
            QualityPreset.SIMPLE_2D: ("Simple 2D", "Minimal effekt på CPU/GPU"),
            QualityPreset.LOW: ("Low", "Grundläggande rendering"),
            QualityPreset.MEDIUM: ("Medium", "Balanserad kvalitet"),
            QualityPreset.HIGH: ("High", "Avancerade effekter"),
            QualityPreset.ULTRA: ("Ultra", "Maximal kvalitet"),
        }
        
        for i, preset in enumerate(self.quality_presets):
            rect = pygame.Rect(x, y + i * (item_height + 8), width, item_height)
            
            is_selected = i == self.selected_quality_idx
            color = self.selected_color if is_selected else self.button_color
            hover_color = self.accent_hover if is_selected else self.button_hover
            
            # Check hover
            mouse_pos = pygame.mouse.get_pos()
            if rect.collidepoint(mouse_pos):
                color = hover_color
            
            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            
            label, desc = quality_labels[preset]
            text = self.font_normal.render(label, True, self.text_color)
            self.screen.blit(text, (rect.x + 10, rect.y + 6))
            
            desc_text = self.font_small.render(desc, True, self.text_dim)
            self.screen.blit(desc_text, (rect.x + 10, rect.y + 22))
            
            self.quality_rects.append((rect, i))
    
    def _draw_display_settings(self, x: int, y: int, width: int) -> None:
        """Draw display settings."""
        self.resolution_rects = []
        item_height = 28
        
        # Resolution label
        res_label = self.font_normal.render("Upplösning:", True, self.text_dim)
        self.screen.blit(res_label, (x, y))
        y += 25
        
        # Resolution options
        for i, (w, h) in enumerate(self.resolutions):
            rect = pygame.Rect(x, y + i * (item_height + 4), width, item_height)
            
            is_selected = i == self.selected_resolution_idx
            color = self.selected_color if is_selected else self.button_color
            
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            
            text = self.font_normal.render(f"{w} x {h}", True, self.text_color)
            self.screen.blit(text, (rect.x + 10, rect.y + 4))
            
            self.resolution_rects.append((rect, i))
        
        y += len(self.resolutions) * (item_height + 4) + 20
        
        # Fullscreen toggle
        self.fullscreen_rect = pygame.Rect(x, y, width, 32)
        color = self.selected_color if self.fullscreen else self.button_color
        
        mouse_pos = pygame.mouse.get_pos()
        if self.fullscreen_rect.collidepoint(mouse_pos):
            color = self.accent_hover if self.fullscreen else self.button_hover
        
        pygame.draw.rect(self.screen, color, self.fullscreen_rect, border_radius=6)
        
        text = self.font_normal.render("Fullskärm", True, self.text_color)
        self.screen.blit(text, (self.fullscreen_rect.x + 10, self.fullscreen_rect.y + 6))
        
        # Checkbox
        cb_rect = pygame.Rect(self.fullscreen_rect.right - 28, self.fullscreen_rect.y + 6, 16, 16)
        pygame.draw.rect(self.screen, self.panel_border, cb_rect, border_radius=2)
        if self.fullscreen:
            pygame.draw.rect(self.screen, self.accent_color, cb_rect.inflate(-4, -4), border_radius=1)
    
    def _draw_start_button(self) -> None:
        """Draw the start simulation button."""
        button_width = 200
        button_height = 50
        x = (self.screen.get_width() - button_width) // 2
        y = self.screen.get_height() - 100
        
        self.start_button_rect = pygame.Rect(x, y, button_width, button_height)
        
        # Check hover
        mouse_pos = pygame.mouse.get_pos()
        color = self.accent_hover if self.start_button_rect.collidepoint(mouse_pos) else self.accent_color
        
        pygame.draw.rect(self.screen, color, self.start_button_rect, border_radius=10)
        
        text = self.font_heading.render("Starta Simulering", True, (255, 255, 255))
        text_rect = text.get_rect(center=self.start_button_rect.center)
        self.screen.blit(text, text_rect)
    
    def _draw_profile_info(self) -> None:
        """Draw selected profile information at bottom."""
        if not self.profiles:
            return
        
        key, name, source = self.profiles[self.selected_profile_idx]
        
        # Get metadata for JSON profiles
        metadata = get_json_profile_metadata(key)
        
        y = self.screen.get_height() - 180
        x = 50
        
        # Info panel background
        info_rect = pygame.Rect(x, y, self.screen.get_width() - 100, 60)
        pygame.draw.rect(self.screen, self.panel_color, info_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.panel_border, info_rect, width=1, border_radius=6)
        
        # Profile details
        cc = self._calculate_cc(key)
        power = metadata.get('stock_power_kw', 0)
        rpm = metadata.get('stock_rpm_peak', 0)
        cooling = metadata.get('cooling', 'air')
        carb = metadata.get('carburetor', '')
        
        info_text = f"{name}  |  {cc:.1f}cc  |  {power}kW @ {rpm}RPM  |  {cooling} cooled"
        if carb:
            info_text += f"  |  {carb}"
        
        text = self.font_normal.render(info_text, True, self.text_color)
        self.screen.blit(text, (x + 15, y + 20))
    
    def _calculate_cc(self, profile_key: str) -> float:
        """Calculate displacement for a profile."""
        # Try to get from profiles
        for key, name, source in self.profiles:
            if key == profile_key:
                # We need to load the actual profile to get B and stroke
                # For now, return approximate values based on known profiles
                if '50' in name and 'stock' in name.lower():
                    return 49.7
                elif '70' in name or '70cc' in name:
                    return 70.0
                elif '80' in name or '80cc' in name:
                    return 80.0
                elif '78' in name:
                    return 78.0
        return 50.0  # Default
