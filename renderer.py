from collections import deque
import math
import pygame
from config import RENDER
from physics.utils import clamp01


def color_rgb(r: float, g: float, b: float) -> tuple[int, int, int]:
    return (
        int(max(0, min(255, r))),
        int(max(0, min(255, g))),
        int(max(0, min(255, b))),
    )


def combustion_palette(lambda_value: float, temperature: float, phase: float) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """Calculate combustion flame colors based on mixture and temperature."""
    lean = clamp01(lambda_value - 1.0)
    rich = clamp01(1.0 - lambda_value)
    heat = clamp01((temperature - 500.0) / 1800.0)
    progress = clamp01(phase)
    outer = color_rgb(255 - 40 * lean, 75 + 90 * heat - 18 * rich, 24 + 120 * lean)
    mid = color_rgb(255, 135 + 80 * heat - 28 * lean, 50 + 95 * lean)
    core = color_rgb(255, 225 + 18 * heat - 12 * rich, 150 + 55 * lean + 18 * progress)
    return outer, mid, core


class EngineRenderer:
    def __init__(self, engine) -> None:
        self.engine = engine
        # Try to load requested font, fall back to default if not available
        try:
            self.font = pygame.font.SysFont("consolas", 18)
            self.small_font = pygame.font.SysFont("consolas", 14)
        except pygame.error:
            # Fallback to default font
            self.font = pygame.font.Font(None, 24)
            self.small_font = pygame.font.Font(None, 18)
        self.cylinder_y = RENDER.crank_y - (engine.R + engine.L) * RENDER.scale
        # Guard against zero A_p (piston area)
        piston_area = max(engine.A_p, 1e-9)
        self.clearance_height_px = engine.V_c / piston_area * RENDER.scale

    def draw(self, screen: pygame.Surface, state, particles, pv_cyl_points: deque, pv_cr_points: deque) -> None:
        screen.fill(RENDER.background_color)
        cyl_w = self.engine.B * RENDER.scale
        cyl_h = 2 * self.engine.R * RENDER.scale + 40
        cyl_left = RENDER.crank_x - cyl_w / 2
        cyl_top = self.cylinder_y - 20
        cyl_rect = pygame.Rect(int(cyl_left), int(cyl_top), int(cyl_w), int(cyl_h))
        cyl_bottom = cyl_rect.bottom
        exh_y = self.cylinder_y + self.engine.x_exh * RENDER.scale
        tr_y = self.cylinder_y + self.engine.x_tr * RENDER.scale
        lambda_value = max(0.7, min(2.5, self.engine.lambda_value))
        burn_phase = self.engine.burn_fraction if self.engine.combustion_active else 0.0
        burn_intensity = clamp01(burn_phase)
        pressure_intensity = clamp01((state.p_cyl - 2.0 * 100000.0) / (14.0 * 100000.0))
        temperature_intensity = clamp01((self.engine.T_cyl - 450.0) / 1800.0)
        pulse_intensity = clamp01((state.p_cyl - 4.0 * 100000.0) / (15.0 * 100000.0))
        retard_deg = max(0.0, self.engine.angle_diff(342.0, self.engine.ignition_angle_deg))
        exhaust_intensity = clamp01(state.dm_exh / 0.18)
        afterburn_fuel = clamp01((1.02 - lambda_value) / 0.35)
        afterburn_timing = clamp01(retard_deg / 22.0)
        afterburn_intensity = clamp01((0.65 * afterburn_fuel + 0.45 * afterburn_timing) * (0.35 + 0.65 * exhaust_intensity) * (0.35 + 0.65 * temperature_intensity))
        outer_flame, mid_flame, core_flame = combustion_palette(lambda_value, self.engine.T_cyl, burn_phase)
        outer_exhaust, mid_exhaust, core_exhaust = combustion_palette(max(0.72, lambda_value * 0.92), self.engine.T_cyl * 0.92, 0.55 + 0.45 * burn_phase)
        exh_col = core_exhaust if state.dm_exh > 0 else (110, 55, 55)
        trans_col = (70, 220, 150) if state.dm_tr > 0 else (60, 110, 90)
        head_rect = pygame.Rect(int(cyl_left - 20), int(cyl_top - 34), int(cyl_w + 40), 34)
        chamber_rect = pygame.Rect(int(cyl_left + 24), int(cyl_top - 10), int(cyl_w - 48), 18)
        crankcase_rect = pygame.Rect(int(RENDER.crank_x - cyl_w * 1.05), int(RENDER.crank_y - self.engine.R * RENDER.scale + 6), int(cyl_w * 2.1), int(self.engine.R * RENDER.scale * 1.95 + 70))
        skirt_rect = pygame.Rect(int(cyl_left + cyl_w * 0.18), cyl_bottom - 2, int(cyl_w * 0.64), crankcase_rect.top - cyl_bottom + 4)
        intake_rect = pygame.Rect(crankcase_rect.left - 78, crankcase_rect.centery - 18, 78, 36)
        reed_open_w = 4 + int(16 * self.engine.reed_opening)
        reed_rect = pygame.Rect(intake_rect.right - reed_open_w, intake_rect.top + 4, reed_open_w, intake_rect.height - 8)
        exhaust_rect = pygame.Rect(cyl_rect.right, int(exh_y), 110, int(self.engine.w_exh * RENDER.scale))
        transfer_rect = pygame.Rect(cyl_rect.left - 54, int(tr_y - 22), 54, int(self.engine.w_tr * RENDER.scale + 58))
        transfer_bridge = [
            (transfer_rect.left + 8, transfer_rect.bottom),
            (transfer_rect.right, transfer_rect.bottom - 10),
            (int(cyl_left + 18), crankcase_rect.top + 28),
            (int(cyl_left - 8), crankcase_rect.top + 34),
        ]
        exhaust_window = pygame.Rect(cyl_rect.right - 8, int(exh_y + 6), 14, max(16, int(self.engine.w_exh * RENDER.scale - 12)))
        transfer_window = pygame.Rect(cyl_rect.left - 6, int(tr_y + 6), 12, max(16, int(self.engine.w_tr * RENDER.scale - 10)))
        structure_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        cylinder_shell_color = (*color_rgb(180 + 36 * pulse_intensity, 180 + 22 * pulse_intensity, 210 + 8 * pulse_intensity), 100 + int(60 * pulse_intensity))
        head_color = (*color_rgb(95 + 125 * pulse_intensity, 95 + 55 * pulse_intensity, 118 + 10 * pulse_intensity), 220)
        pygame.draw.rect(structure_surface, cylinder_shell_color, cyl_rect, border_radius=10)
        pygame.draw.rect(structure_surface, head_color, head_rect, border_radius=10)
        pygame.draw.ellipse(structure_surface, (52, 52, 68, 235), crankcase_rect)
        pygame.draw.rect(structure_surface, (72, 72, 92, 220), skirt_rect, border_radius=14)
        pygame.draw.rect(structure_surface, (65, 50, 50, 220), exhaust_rect, border_radius=10)
        pygame.draw.rect(structure_surface, (48, 78, 98, 220), transfer_rect, border_radius=10)
        pygame.draw.polygon(structure_surface, (48, 78, 98, 220), transfer_bridge)
        pygame.draw.rect(structure_surface, (58, 92, 64, 220), intake_rect, border_radius=8)
        pygame.draw.rect(structure_surface, (210, 180, 90, 220), reed_rect, border_radius=4)
        pygame.draw.rect(structure_surface, (32, 28, 38, 255), chamber_rect, border_radius=8)
        pygame.draw.rect(structure_surface, exh_col, exhaust_window, border_radius=5)
        pygame.draw.rect(structure_surface, trans_col, transfer_window, border_radius=5)
        screen.blit(structure_surface, (0, 0))
        if pulse_intensity > 0.03:
            pulse_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            for inflate_px, alpha_scale in ((6, 0.16), (12, 0.11), (18, 0.07)):
                pulse_rect = cyl_rect.inflate(inflate_px, inflate_px)
                pulse_head = head_rect.inflate(inflate_px + 8, inflate_px)
                pulse_alpha = int(255 * pulse_intensity * alpha_scale)
                pulse_color = (*core_flame, pulse_alpha)
                pygame.draw.rect(pulse_surface, pulse_color, pulse_rect, width=3, border_radius=12)
                pygame.draw.rect(pulse_surface, pulse_color, pulse_head, width=3, border_radius=12)
            screen.blit(pulse_surface, (0, 0))
        pygame.draw.rect(screen, color_rgb(112 + 110 * pulse_intensity, 112 + 45 * pulse_intensity, 138 + 12 * pulse_intensity), cyl_rect, width=4, border_radius=10)
        pygame.draw.rect(screen, color_rgb(130 + 95 * pulse_intensity, 130 + 48 * pulse_intensity, 150 + 8 * pulse_intensity), head_rect, width=3, border_radius=10)
        pygame.draw.ellipse(screen, (100, 100, 122), crankcase_rect, width=4)
        pygame.draw.rect(screen, (98, 98, 118), skirt_rect, width=3, border_radius=14)
        pygame.draw.rect(screen, (108, 76, 76), exhaust_rect, width=3, border_radius=10)
        pygame.draw.rect(screen, (76, 118, 132), transfer_rect, width=3, border_radius=10)
        pygame.draw.lines(screen, (76, 118, 132), True, transfer_bridge, 3)
        pygame.draw.rect(screen, (82, 122, 90), intake_rect, width=3, border_radius=8)
        pygame.draw.rect(screen, (230, 200, 120), reed_rect, width=2, border_radius=4)
        spark_body = pygame.Rect(RENDER.crank_x - 10, head_rect.top - 18, 20, 24)
        pygame.draw.rect(screen, (210, 210, 220), spark_body, border_radius=5)
        pygame.draw.line(screen, (240, 240, 245), (RENDER.crank_x, spark_body.bottom), (RENDER.crank_x, chamber_rect.top + 2), 4)
        glow_intensity = max(burn_intensity, pressure_intensity * 0.8, temperature_intensity * 0.75)
        if glow_intensity > 0.01:
            combustion_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            chamber_center = (RENDER.crank_x, chamber_rect.centery + 2)
            max_radius = max(18, int(cyl_w * (0.18 + 0.30 * glow_intensity)))
            for radius_scale, alpha_scale, color in (
                (1.55, 0.18, outer_flame),
                (1.20, 0.28, mid_flame),
                (0.82, 0.40, core_flame),
            ):
                radius = max(8, int(max_radius * radius_scale))
                alpha = int(255 * glow_intensity * alpha_scale)
                pygame.draw.circle(combustion_surface, (*color, alpha), chamber_center, radius)
            piston_y_for_glow = self.cylinder_y + self.clearance_height_px + state.x * RENDER.scale
            flame_height = max(12, int((piston_y_for_glow - chamber_rect.bottom) * (0.18 + 0.55 * glow_intensity)))
            flame_rect = pygame.Rect(int(cyl_left + 6), chamber_rect.bottom - 2, int(cyl_w - 12), flame_height)
            pygame.draw.ellipse(combustion_surface, (*mid_flame, int(120 * glow_intensity)), flame_rect)
            screen.blit(combustion_surface, (0, 0))
        if self.engine.spark_active:
            pygame.draw.circle(screen, (255, 255, 150), (RENDER.crank_x, chamber_rect.centery), 18)
        if glow_intensity > 0.04:
            flame_kernel_radius = max(10, int(10 + burn_intensity * 34 + pressure_intensity * 12))
            flame_kernel_center = (RENDER.crank_x, chamber_rect.centery + int(6 + state.x * RENDER.scale * 0.08))
            pygame.draw.circle(screen, core_flame, flame_kernel_center, flame_kernel_radius)
            pygame.draw.circle(screen, mid_flame, flame_kernel_center, max(5, int(flame_kernel_radius * 0.62)))
        if afterburn_intensity > 0.04:
            exhaust_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            flame_length = int(55 + 130 * afterburn_intensity + 20 * exhaust_intensity)
            flame_center_y = exhaust_rect.centery + int(math.sin(self.engine.theta * 2.0) * 4)
            outer_rect = pygame.Rect(exhaust_rect.right - 8, flame_center_y - 18, flame_length, 36)
            mid_rect = pygame.Rect(exhaust_rect.right + 4, flame_center_y - 14, int(flame_length * 0.72), 28)
            core_rect = pygame.Rect(exhaust_rect.right + 14, flame_center_y - 9, int(flame_length * 0.44), 18)
            pygame.draw.ellipse(exhaust_surface, (*outer_exhaust, int(140 * afterburn_intensity)), outer_rect)
            pygame.draw.ellipse(exhaust_surface, (*mid_exhaust, int(180 * afterburn_intensity)), mid_rect)
            pygame.draw.ellipse(exhaust_surface, (*core_exhaust, int(210 * afterburn_intensity)), core_rect)
            screen.blit(exhaust_surface, (0, 0))
        piston_y = self.cylinder_y + self.clearance_height_px + state.x * RENDER.scale
        piston_rect = pygame.Rect(int(cyl_left + 2), int(piston_y), int(cyl_w - 4), int(RENDER.piston_height_px))
        pygame.draw.rect(screen, RENDER.piston_color, piston_rect, border_radius=3)
        crank_x = RENDER.crank_x + math.sin(self.engine.theta) * self.engine.R * RENDER.scale
        crank_y = RENDER.crank_y - math.cos(self.engine.theta) * self.engine.R * RENDER.scale
        piston_pin = (RENDER.crank_x, piston_rect.y + RENDER.piston_height_px / 2)
        pygame.draw.line(screen, (150, 150, 170), (crank_x, crank_y), piston_pin, 14)
        pygame.draw.line(screen, (180, 180, 200), (RENDER.crank_x, RENDER.crank_y), (crank_x, crank_y), 20)
        pygame.draw.circle(screen, (200, 50, 50), (int(crank_x), int(crank_y)), 8)
        pygame.draw.circle(screen, (50, 50, 50), (int(piston_pin[0]), int(piston_pin[1])), 6)
        particle_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        # Separate particles into standard and additive blending layers
        additive_particles = []
        standard_particles = []
        
        for particle in particles:
            if particle.life > 0:
                if particle.region in ["cylinder", "exhaust"]:
                    additive_particles.append(particle)
                else:
                    standard_particles.append(particle)
                    
        for particle in standard_particles:
            color = (*particle.color, int(particle.life))
            pygame.draw.circle(particle_surface, color, (int(particle.x), int(particle.y)), int(particle.size))
            
        screen.blit(particle_surface, (0, 0))
        
        if additive_particles:
            additive_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            for particle in additive_particles:
                color = (*particle.color, int(particle.life))
                pygame.draw.circle(additive_surface, color, (int(particle.x), int(particle.y)), int(particle.size))
                # Add dynamic glow to hot particles
                if particle.life > 150:
                    glow_color = (*particle.color, int(particle.life * 0.3))
                    pygame.draw.circle(additive_surface, glow_color, (int(particle.x), int(particle.y)), int(particle.size * 2.5))
            screen.blit(additive_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        afr = 1.0 / self.engine.fuel_ratio if self.engine.fuel_ratio > 0 else 0.0
        ignition_status = "PÅ" if self.engine.ignition_enabled else "AV"
        fuel_status = "AV" if self.engine.fuel_cutoff else "PÅ"
        texts = [
            f"Gaspådrag: {int(self.engine.throttle * 100)}% [Upp/Ner]",
            f"Bränsleblandning: AFR {afr:.1f}:1 [PgUp/PgDn]",
            f"Tomgångsbränsle: {self.engine.idle_fuel_trim:.2f}x [Home/End]",
            f"Tändvinkel: {int(self.engine.ignition_angle_deg)}° [Vänster/Höger]",
            f"Tändning: {ignition_status} [I]",
            f"Bränsle: {fuel_status} [K]",
            f"RPM: {int(state.rpm)}",
            f"Effekt: {state.power_kw:.2f} kW ({state.power_kw * 1.36:.2f} hk)",
            f"Nettomoment: {state.torque:.2f} Nm",
            f"Cyl Tryck: {state.p_cyl / 100000:.2f} Bar",
            f"Vevhus Tryck: {state.p_cr / 100000:.2f} Bar",
            f"Avgasrör Tryck: {state.p_exh_pipe / 100000:.2f} Bar",
            f"Förbränning: {int(self.engine.burn_fraction * 100)}%",
            f"Lambda: {self.engine.lambda_value:.2f}",
            f"Volumetric Eff (VE): {int(state.volumetric_efficiency * 100)}%",
            f"Trapping Eff (TE): {int(state.trapping_efficiency * 100)}%",
            f"Insug: {state.dm_air_in * 1000:.1f}g luft / {state.dm_fuel_in * 1000:.2f}g bränsle",
            f"Transfer: {state.dm_air_tr * 1000:.1f}g luft / {state.dm_fuel_tr * 1000:.2f}g br",
            f"Avgas: {state.dm_air_exh * 1000:.1f}g luft / {state.dm_fuel_exh * 1000:.2f}g br / {state.dm_burned_exh * 1000:.1f}g rest",
        ]
        for index, text in enumerate(texts):
            screen.blit(self.font.render(text, True, (220, 220, 230)), (20, 20 + index * 22))
        diag_rect = (900, 30, 350, 280)
        pygame.draw.rect(screen, (30, 30, 40), diag_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), diag_rect, width=2, border_radius=8)
        screen.blit(self.small_font.render("PV-Diagram Cylinder (cc vs Bar)", True, (200, 200, 200)), (910, 40))
        if len(pv_cyl_points) > 2:
            mapped = []
            for volume, pressure in pv_cyl_points:
                px = 900 + ((volume - 15) / 130) * 350
                py = 310 - (min(pressure, 80) / 80) * 280
                mapped.append((px, py))
            pygame.draw.lines(screen, (255, 120, 120), False, mapped, 2)
        diag2_rect = (900, 350, 350, 280)
        pygame.draw.rect(screen, (30, 40, 30), diag2_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), diag2_rect, width=2, border_radius=8)
        screen.blit(self.small_font.render("PV-Diagram Vevhus (cc vs Bar)", True, (200, 200, 200)), (910, 360))
        if len(pv_cr_points) > 2:
            mapped2 = []
            for volume, pressure in pv_cr_points:
                px = 900 + ((volume - 240) / 120) * 350
                py = 630 - ((pressure - 0.5) / 1.0) * 280
                mapped2.append((px, py))
            pygame.draw.lines(screen, (120, 255, 120), False, mapped2, 2)
