from collections import deque

import pygame

import config as config_module
import particles as particles_module
import renderer as renderer_module
from config import WINDOW, QualityPreset, get_quality_preset, TuningPreset, apply_tuning_preset, save_tuning_preset
from particles import spawn_particles, update_particles
from physics import EnginePhysics
from renderer import EngineRenderer
from ui import MainMenu
from engine_profiles import apply_profile

SUBSTEPS = 10
PHYSICS_DT = 1.0 / 600.0  # Fixed physics timestep for stable simulation


def apply_render_config(new_config) -> None:
    """Propagate render configuration to all modules that cache the RENDER object."""
    config_module.RENDER = new_config
    particles_module.RENDER = new_config
    renderer_module.RENDER = new_config


class EngineApp:
    def __init__(self, profile_key: str = "am6_stock", quality_preset: QualityPreset = QualityPreset.SIMPLE_2D) -> None:
        # Initialize with selected profile and quality
        new_config = get_quality_preset(quality_preset)
        apply_render_config(new_config)
        
        self._current_preset = quality_preset
        self._presets = [
            QualityPreset.SIMPLE_2D,
            QualityPreset.LOW,
            QualityPreset.MEDIUM,
            QualityPreset.HIGH,
            QualityPreset.ULTRA,
        ]
        
        self.engine = EnginePhysics()
        # Apply selected profile
        apply_profile(self.engine, profile_key)
        
        self.renderer = EngineRenderer(self.engine)
        self.particles = []
        self.pv_cyl_points: deque[tuple[float, float]] = deque(maxlen=300)
        self.pv_cr_points: deque[tuple[float, float]] = deque(maxlen=300)
        self.running = True
        self.paused = False
        self.slow_mo = 1.0
        self._physics_accumulator = 0.0
        self._starter_pressed = False
        self.state = self.engine.snapshot()
        self._profile_key = profile_key
        self._quality_preset = quality_preset

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.engine.throttle = min(1.0, self.engine.throttle + 0.01)
            elif event.key == pygame.K_DOWN:
                self.engine.throttle = max(0.0, self.engine.throttle - 0.01)
            elif event.key == pygame.K_LEFT:
                self.engine.ignition_angle_deg = (self.engine.ignition_angle_deg - 5) % 360
            elif event.key == pygame.K_RIGHT:
                self.engine.ignition_angle_deg = (self.engine.ignition_angle_deg + 5) % 360
            elif event.key == pygame.K_PAGEUP:
                self.engine.fuel_ratio = min(0.15, self.engine.fuel_ratio + 0.01)
            elif event.key == pygame.K_PAGEDOWN:
                self.engine.fuel_ratio = max(0.02, self.engine.fuel_ratio - 0.01)
            elif event.key == pygame.K_HOME:
                self.engine.idle_fuel_trim = min(2.0, self.engine.idle_fuel_trim + 0.02)
            elif event.key == pygame.K_END:
                self.engine.idle_fuel_trim = max(0.4, self.engine.idle_fuel_trim - 0.02)
            elif event.key == pygame.K_p:
                self.paused = not self.paused
            elif event.key == pygame.K_i:
                self.engine.ignition_enabled = not self.engine.ignition_enabled
            elif event.key == pygame.K_k:
                self.engine.fuel_cutoff = not self.engine.fuel_cutoff
            elif event.key == pygame.K_s:
                self._starter_pressed = True
            elif event.key == pygame.K_F1:
                self._cycle_preset(0)
            elif event.key == pygame.K_F2:
                self._cycle_preset(1)
            elif event.key == pygame.K_F3:
                self._cycle_preset(2)
            elif event.key == pygame.K_F4:
                self._cycle_preset(3)
            elif event.key == pygame.K_F5:
                self._cycle_preset(4)
            # Tuning presets (1-5)
            elif event.key == pygame.K_1:
                apply_tuning_preset(self.engine, TuningPreset.STOCK)
                print("Tuning: Stock")
            elif event.key == pygame.K_2:
                apply_tuning_preset(self.engine, TuningPreset.GATTRIM)
                print("Tuning: Gattrim")
            elif event.key == pygame.K_3:
                apply_tuning_preset(self.engine, TuningPreset.RACING)
                print("Tuning: Racing")
            elif event.key == pygame.K_4:
                apply_tuning_preset(self.engine, TuningPreset.CLASSIC)
                print("Tuning: Classic")
            elif event.key == pygame.K_5:
                apply_tuning_preset(self.engine, TuningPreset.DRAGRACE)
                print("Tuning: Dragrace")
            # Nya trimningsparametrar
            elif event.key == pygame.K_6:
                # Justera kompression
                self.engine.compression_ratio = min(10.0, self.engine.compression_ratio + 0.5)
                print(f"Compression: {self.engine.compression_ratio:.1f}:1")
            elif event.key == pygame.K_7:
                self.engine.compression_ratio = max(6.0, self.engine.compression_ratio - 0.5)
                print(f"Compression: {self.engine.compression_ratio:.1f}:1")
            elif event.key == pygame.K_8:
                # Justera avgaspipa resonans
                self.engine.pipe_resonance_freq = min(200.0, self.engine.pipe_resonance_freq + 10.0)
                print(f"Pipe freq: {self.engine.pipe_resonance_freq:.0f} Hz")
            elif event.key == pygame.K_9:
                self.engine.pipe_resonance_freq = max(80.0, self.engine.pipe_resonance_freq - 10.0)
                print(f"Pipe freq: {self.engine.pipe_resonance_freq:.0f} Hz")
            elif event.key == pygame.K_0:
                # Spara nuvarande inställningar
                save_tuning_preset(self.engine, "my_tune")
                print("Sparade inställningar till my_tune.json")
            # Fler parametrar med Shift
            elif event.key == pygame.K_MINUS and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.engine.stroke_multiplier = max(0.8, self.engine.stroke_multiplier - 0.05)
                print(f"Stroke: {self.engine.stroke_multiplier:.2f}")
            elif event.key == pygame.K_EQUALS and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.engine.stroke_multiplier = min(1.2, self.engine.stroke_multiplier + 0.05)
                print(f"Stroke: {self.engine.stroke_multiplier:.2f}")
            elif event.key == pygame.K_LEFTBRACKET:
                self.engine.transfer_port_height = max(0.025, self.engine.transfer_port_height - 0.002)
                print(f"Transfer port: {self.engine.transfer_port_height:.3f}m")
            elif event.key == pygame.K_RIGHTBRACKET:
                self.engine.transfer_port_height = min(0.045, self.engine.transfer_port_height + 0.002)
                print(f"Transfer port: {self.engine.transfer_port_height:.3f}m")
            elif event.key == pygame.K_SEMICOLON:
                self.engine.exhaust_port_height = max(0.018, self.engine.exhaust_port_height - 0.002)
                print(f"Exhaust port: {self.engine.exhaust_port_height:.3f}m")
            elif event.key == pygame.K_QUOTE:
                self.engine.exhaust_port_height = min(0.035, self.engine.exhaust_port_height + 0.002)
                print(f"Exhaust port: {self.engine.exhaust_port_height:.3f}m")
            elif event.key == pygame.K_COMMA:
                self.engine.reed_stiffness = max(800.0, self.engine.reed_stiffness - 100.0)
                print(f"Reed stiffness: {self.engine.reed_stiffness:.0f}")
            elif event.key == pygame.K_PERIOD:
                self.engine.reed_stiffness = min(2000.0, self.engine.reed_stiffness + 100.0)
                print(f"Reed stiffness: {self.engine.reed_stiffness:.0f}")
            elif event.key == pygame.K_SLASH:
                self.engine.inertia_multiplier = max(0.6, self.engine.inertia_multiplier - 0.1)
                print(f"Inertia: {self.engine.inertia_multiplier:.1f}")
            elif event.key == pygame.K_BACKSLASH:
                self.engine.inertia_multiplier = min(1.5, self.engine.inertia_multiplier + 0.1)
                print(f"Inertia: {self.engine.inertia_multiplier:.1f}")
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_s:
                self._starter_pressed = False

    def _cycle_preset(self, index: int) -> None:
        """Switch to a different rendering quality preset."""
        if 0 <= index < len(self._presets):
            self._current_preset = self._presets[index]
            new_config = get_quality_preset(self._current_preset)
            apply_render_config(new_config)
            self.renderer = renderer_module.EngineRenderer(self.engine)
            print(f"Rendering preset: {self._current_preset.value}")

    def restart_simulation(self) -> None:
        """Restart the simulation with current profile and settings."""
        # Reset engine with same profile
        self.engine = EnginePhysics()
        apply_profile(self.engine, self._profile_key)
        
        # Reset state tracking
        self.pv_cyl_points.clear()
        self.pv_cr_points.clear()
        self._physics_accumulator = 0.0
        self._starter_pressed = False
        self.paused = False
        
        # Recreate renderer for new engine
        self.renderer = EngineRenderer(self.engine)
        self.state = self.engine.snapshot()
        
        print(f"Simulation restarted with profile: {self._profile_key}")

    def update(self, raw_dt: float) -> None:
        if self.paused:
            self.particles = update_particles(self.particles, self.state, self.engine, self.renderer.cylinder_y)
            return
        # Accumulate time and step physics with fixed timestep
        self._physics_accumulator += raw_dt
        while self._physics_accumulator >= PHYSICS_DT:
            self.state = self.engine.step(PHYSICS_DT, self._starter_pressed)
            spawn_particles(self.particles, self.state, self.engine, self.renderer.cylinder_y)
            self.particles = update_particles(self.particles, self.state, self.engine, self.renderer.cylinder_y)
            self._physics_accumulator -= PHYSICS_DT
        v_cyl_cc = (self.engine.V_c + self.engine.A_p * self.state.x) * 1e6
        v_cr_cc = (self.engine.V_cr_min + self.engine.A_p * (2 * self.engine.R - self.state.x)) * 1e6
        self.pv_cyl_points.append((v_cyl_cc, self.state.p_cyl / 100000.0))
        self.pv_cr_points.append((v_cr_cc, self.state.p_cr / 100000.0))

    def render(self) -> None:
        dt = self.clock.get_time() / 1000.0
        self.renderer.draw(self.screen, self.state, self.particles, self.pv_cyl_points, self.pv_cr_points, dt)
        
        # Draw pause overlay if paused
        if self.paused:
            self._draw_pause_overlay()
        
        pygame.display.flip()
    
    def _draw_pause_overlay(self) -> None:
        """Draw pause menu overlay."""
        # Semi-transparent background
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.screen.blit(overlay, (0, 0))
        
        # Pause text
        font_title = pygame.font.SysFont("Arial", 48, bold=True)
        font_option = pygame.font.SysFont("Arial", 28)
        
        text = font_title.render("PAUSAD", True, (255, 255, 255))
        rect = text.get_rect(center=(self.screen.get_width() // 2, 200))
        self.screen.blit(text, rect)
        
        # Instructions
        instructions = [
            "ESC/P - Fortsätt",
            "R - Starta om simulering",
            "M - Huvudmeny",
        ]
        y = 280
        for instruction in instructions:
            text = font_option.render(instruction, True, (200, 200, 200))
            rect = text.get_rect(center=(self.screen.get_width() // 2, y))
            self.screen.blit(text, rect)
            y += 40

    def run(self, screen: pygame.Surface, clock: pygame.time.Clock) -> None:
        """Run the simulation loop with provided screen and clock."""
        self.screen = screen
        self.clock = clock
        
        while self.running:
            raw_dt = self.clock.tick(WINDOW.fps) / 1000.0 * self.slow_mo
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                
                # Handle pause menu keys even when paused
                if event.type == pygame.KEYDOWN:
                    if self.paused:
                        if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                            self.paused = False
                            continue
                        elif event.key == pygame.K_r:
                            self.restart_simulation()
                            continue
                        elif event.key == pygame.K_m:
                            # Return to main menu
                            self.running = False
                            return "main_menu"
                    else:
                        if event.key == pygame.K_ESCAPE:
                            self.paused = True
                            continue
                
                # Only process simulation inputs when not paused
                if not self.paused:
                    self.handle_event(event)
            
            self.update(raw_dt)
            self.render()
        
        return "quit"


def run() -> None:
    """Main entry point - shows main menu then runs simulation loop."""
    # Initialize PyGame once at module level
    try:
        pygame.init()
    except pygame.error as e:
        raise RuntimeError(f"Failed to initialize PyGame: {e}")
    
    pygame.key.set_repeat(140, 25)
    
    # Create initial window for main menu
    try:
        screen = pygame.display.set_mode((WINDOW.width, WINDOW.height))
    except pygame.error as e:
        raise RuntimeError(f"Failed to create display: {e}")
    
    pygame.display.set_caption(WINDOW.title)
    clock = pygame.time.Clock()
    
    # Main loop - allow returning to menu after simulation
    while True:
        # Show main menu
        menu = MainMenu(screen, lambda pk, qp: None)  # Callback not used directly
        menu.running = True
        menu.run()
        
        # Get selected settings
        profile_key = menu.profiles[menu.selected_profile_idx][0] if menu.profiles else "am6_stock"
        quality_preset = menu.quality_presets[menu.selected_quality_idx]
        
        # Clear event queue after menu exits
        pygame.event.pump()
        for event in pygame.event.get():
            pass  # Discard all pending events
        
        # Apply display settings if changed
        resolution = menu.resolutions[menu.selected_resolution_idx]
        if menu.fullscreen:
            screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN)
        else:
            # Only resize if different from current
            current_size = screen.get_size()
            if current_size != resolution:
                screen = pygame.display.set_mode(resolution)
        
        # Start simulation with selected settings
        app = EngineApp(profile_key, quality_preset)
        result = app.run(screen, clock)
        
        if result == "quit":
            break
        # If "main_menu", loop continues and shows menu again
    
    pygame.quit()
