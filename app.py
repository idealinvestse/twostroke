from collections import deque

import pygame

from config import WINDOW
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
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_s:
                self._starter_pressed = False

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
        self.renderer.draw(self.screen, self.state, self.particles, self.pv_cyl_points, self.pv_cr_points)
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
