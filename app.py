from collections import deque

import pygame

from config import WINDOW, QualityPreset, get_quality_preset, TuningPreset, apply_tuning_preset, save_tuning_preset
from particles import spawn_particles, update_particles
from physics import EnginePhysics
from renderer import EngineRenderer

SUBSTEPS = 10
PHYSICS_DT = 1.0 / 600.0  # Fixed physics timestep for stable simulation


class EngineApp:
    def __init__(self) -> None:
        try:
            pygame.init()
        except pygame.error as e:
            raise RuntimeError(f"Failed to initialize PyGame: {e}")
        
        pygame.key.set_repeat(140, 25)
        
        try:
            self.screen = pygame.display.set_mode((WINDOW.width, WINDOW.height))
        except pygame.error as e:
            raise RuntimeError(f"Failed to create display: {e}")
        
        pygame.display.set_caption(WINDOW.title)
        self.clock = pygame.time.Clock()
        self.engine = EnginePhysics()
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
        self._current_preset = QualityPreset.SIMPLE_2D
        self._presets = [
            QualityPreset.SIMPLE_2D,
            QualityPreset.LOW,
            QualityPreset.MEDIUM,
            QualityPreset.HIGH,
            QualityPreset.ULTRA,
        ]

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
                print(f"Tuning: Stock")
            elif event.key == pygame.K_2:
                apply_tuning_preset(self.engine, TuningPreset.GATTRIM)
                print(f"Tuning: Gattrim")
            elif event.key == pygame.K_3:
                apply_tuning_preset(self.engine, TuningPreset.RACING)
                print(f"Tuning: Racing")
            elif event.key == pygame.K_4:
                apply_tuning_preset(self.engine, TuningPreset.CLASSIC)
                print(f"Tuning: Classic")
            elif event.key == pygame.K_5:
                apply_tuning_preset(self.engine, TuningPreset.DRAGRACE)
                print(f"Tuning: Dragrace")
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
            global RENDER
            RENDER = new_config
            self.renderer = EngineRenderer(self.engine)
            print(f"Rendering preset: {self._current_preset.value}")

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
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            raw_dt = self.clock.tick(WINDOW.fps) / 1000.0 * self.slow_mo
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(raw_dt)
            self.render()
        pygame.quit()


def run() -> None:
    EngineApp().run()
