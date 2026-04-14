import math
import random
from dataclasses import dataclass

from config import RENDER
from physics.utils import clamp01

# Scale factor for piston velocity calculation (converts physics to visual units)
PISTON_VEL_SCALE = 0.01

# Transfer port top boundary offset (matches visual drawing in renderer)
TRANSFER_PORT_TOP_OFFSET = 20.0




def combustion_particle_colors(lambda_value: float, temperature: float, phase: float) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """Calculate combustion colors - delegates to renderer's palette."""
    # Import here to avoid circular imports
    from renderer import combustion_palette
    return combustion_palette(lambda_value, temperature, phase)


def validate_particle(particle: 'Particle') -> bool:
    """Check if particle properties are valid (no NaN/infinity).
    Returns True if valid, False otherwise."""
    if not math.isfinite(particle.x) or not math.isfinite(particle.y):
        return False
    if not math.isfinite(particle.vx) or not math.isfinite(particle.vy):
        return False
    if not math.isfinite(particle.life) or not math.isfinite(particle.size):
        return False
    if particle.life < 0 or particle.size < 0:
        return False
    return True




@dataclass
class Particle:
    x: float
    y: float
    color: tuple[int, int, int]
    vx: float
    vy: float
    fade_speed: float = 8.0
    life: float = 255.0
    size: float = 3.0
    region: str = "cylinder"
    swirl_phase: float = 0.0
    swirl_speed: float = 0.0
    p_type: str = "air"
    temperature: float = 293.0
    initial_size: float = 3.0

    def __post_init__(self) -> None:
        if self.size == 3.0:
            self.size = random.uniform(1.0, 2.5)
        self.initial_size = self.size
        self.swirl_phase = random.uniform(0.0, math.pi * 2)
        self.swirl_speed = random.uniform(0.03, 0.1)
        if self.p_type in ("flame", "spark"):
            self.temperature = random.uniform(1200.0, 2000.0)
        elif self.p_type == "fuel":
            self.temperature = random.uniform(293.0, 450.0)

    def update(self, engine_temp: float = 293.0) -> None:
        # Add micro-turbulence (reduced for more fluid movement)
        self.swirl_phase += self.swirl_speed
        turb_x = math.sin(self.swirl_phase) * 0.1
        turb_y = math.cos(self.swirl_phase) * 0.1
        
        # v2.1: Turbulence-dependent movement (more chaotic at higher velocities)
        speed = math.hypot(self.vx, self.vy)
        if speed > 5.0:
            turb_scale = min(2.0, speed / 10.0)
            turb_x *= turb_scale
            turb_y *= turb_scale
        
        # Air drag (increased for more realistic deceleration)
        # Size-dependent drag: smaller particles experience more drag
        size_factor = max(0.5, min(1.5, 2.0 / max(self.size, 0.1)))
        base_drag = 0.94 if self.region != "cylinder" else 0.96
        drag = base_drag ** size_factor
        self.vx *= drag
        self.vy *= drag
        
        # Temperature-based buoyancy (hot particles rise)
        if self.temperature > 400.0:
            buoyancy = (self.temperature - 400.0) / 1600.0 * 0.15
            self.vy -= buoyancy
        
        # Thermophoresis: particles move away from hot areas
        if self.p_type not in ("flame", "spark") and engine_temp > 600.0:
            thermophoretic_strength = (engine_temp - 600.0) / 1200.0 * 0.08
            if self.region == "cylinder":
                self.vy -= thermophoretic_strength
        
        # Gravity for fuel droplets (reduced)
        if self.p_type == "fuel":
            self.vy += 0.08
            # Evaporation: fuel droplets shrink over time
            if self.initial_size > 0.5:
                evaporation_rate = 0.003 * (self.temperature - 293.0) / 700.0
                self.size = max(0.5, self.size - evaporation_rate)
                if self.size < self.initial_size * 0.3:
                    self.p_type = "vapor"
                    self.color = (180, 180, 200)
        
        # v2.1: Sparks decay faster and have different physics
        if self.p_type == "spark":
            self.life -= self.fade_speed * 2.0  # Faster decay
            self.vy += 0.15  # More gravity
            self.temperature = max(293.0, self.temperature - 25.0)
        
        # Flame particles cool down over time
        if self.p_type == "flame":
            self.temperature = max(293.0, self.temperature - 15.0)
            # Size shrinks as flame cools
            temp_ratio = (self.temperature - 293.0) / 1707.0
            self.size = self.initial_size * (0.3 + 0.7 * temp_ratio)
        
        self.x += self.vx + turb_x
        self.y += self.vy + turb_y
        self.life -= self.fade_speed


def spawn_particles(particles: list[Particle], state, engine, cylinder_y: float) -> None:
    max_particles = getattr(RENDER, "max_particles", 0)
    remaining_particles = max(0, max_particles - len(particles)) if max_particles > 0 else None
    if remaining_particles == 0:
        return

    def reserve(count: int) -> int:
        nonlocal remaining_particles
        if count <= 0:
            return 0
        if remaining_particles is None:
            return count
        if remaining_particles <= 0:
            return 0
        allowed = min(count, remaining_particles)
        remaining_particles -= allowed
        return allowed

    lambda_value = max(0.7, min(2.5, engine.lambda_value))
    burn_phase = engine.burn_fraction if engine.combustion_active else 0.0
    burn_intensity = max(0.0, min(1.0, burn_phase))
    pressure_intensity = max(0.0, min(1.0, (state.p_cyl - 2.0 * 100000.0) / (14.0 * 100000.0)))
    retard_deg = max(0.0, engine.angle_diff(342.0, engine.ignition_angle_deg))
    exhaust_intensity = max(0.0, min(1.0, state.dm_exh / 0.18))
    afterburn_fuel = clamp01((1.02 - lambda_value) / 0.35)
    afterburn_timing = clamp01(retard_deg / 22.0)
    temperature_intensity = clamp01((engine.T_cyl - 450.0) / 1800.0)
    afterburn_intensity = clamp01((0.65 * afterburn_fuel + 0.45 * afterburn_timing) * (0.35 + 0.65 * exhaust_intensity) * (0.35 + 0.65 * temperature_intensity))
    outer_flame, mid_flame, core_flame = combustion_particle_colors(lambda_value, engine.T_cyl, burn_phase)
    outer_exhaust, mid_exhaust, core_exhaust = combustion_particle_colors(max(0.72, lambda_value * 0.92), engine.T_cyl * 0.9, 0.45 + 0.55 * burn_phase)
    
    # v2.1: Temperature-based color gradation for air/fuel particles
    def temp_based_color(base_color: tuple[int, int, int], temp: float) -> tuple[int, int, int]:
        """Adjust color based on temperature (blue cold → red hot)."""
        temp_norm = clamp01((temp - 293.0) / 1000.0)  # 293K-1293K range
        r, g, b = base_color
        # Shift towards red at high temperature
        r = min(255, int(r + 50 * temp_norm))
        g = max(0, int(g - 30 * temp_norm))
        b = max(0, int(b - 50 * temp_norm))
        return (r, g, b)
    
    crankcase_top = RENDER.crank_y - engine.R * RENDER.scale + 6

    if state.dm_exh > 0 and random.random() < state.dm_exh * 0.002 * 40000:
        exh_y = cylinder_y + engine.x_exh * RENDER.scale + 6
        for _ in range(reserve(random.randint(1, 3))):
            particles.append(
                Particle(
                    x=RENDER.crank_x + engine.B / 2 * RENDER.scale,
                    y=exh_y + random.uniform(0, engine.w_exh * RENDER.scale - 12),
                    color=(100, 100, 100),
                    vx=random.uniform(10, 25),
                    vy=random.uniform(-3, 3),
                    region="exhaust",
                    fade_speed=random.uniform(2.0, 5.0),
                    p_type="exhaust",
                    temperature=random.uniform(500.0, 800.0)
                )
            )
    elif state.dm_exh < 0 and random.random() < abs(state.dm_exh) * 0.002 * 40000:
        exh_y = cylinder_y + engine.x_exh * RENDER.scale + 6
        for _ in range(reserve(random.randint(1, 3))):
            particles.append(
                Particle(
                    x=RENDER.crank_x + engine.B / 2 * RENDER.scale + 40,
                    y=exh_y + random.uniform(0, engine.w_exh * RENDER.scale - 12),
                    color=(110, 110, 110),
                    vx=random.uniform(-25, -10),
                    vy=random.uniform(-3, 3),
                    region="exhaust",
                    fade_speed=random.uniform(2.0, 5.0),
                    p_type="exhaust",
                    temperature=random.uniform(400.0, 700.0)
                )
            )
    if engine.spark_active or burn_intensity > 0.02:
        flame_count = reserve(1 + int(12 * max(burn_intensity, pressure_intensity)))
        # Guard against zero A_p (piston area)
        piston_area = max(engine.A_p, 1e-9)
        piston_y = cylinder_y + engine.V_c / piston_area * RENDER.scale + state.x * RENDER.scale
        chamber_top = cylinder_y
        chamber_bottom = max(chamber_top + 10, piston_y - 15)
        
        # v2.1: Add sparks at ignition
        if engine.spark_active:
            spark_count = reserve(3 + int(5 * pressure_intensity))
            for _ in range(spark_count):
                particles.append(
                    Particle(
                        x=RENDER.crank_x + random.uniform(-5, 5),
                        y=chamber_top + random.uniform(0, 10),
                        color=(255, 255, 200),
                        vx=random.uniform(-15.0, 15.0),
                        vy=random.uniform(-10.0, 5.0),
                        fade_speed=random.uniform(15.0, 25.0),
                        life=random.uniform(80.0, 150.0),
                        size=random.uniform(1.0, 2.0),
                        region="cylinder",
                        p_type="spark",
                        temperature=random.uniform(1800.0, 2500.0)
                    )
                )
        
        for _ in range(flame_count):
            flame_color = random.choice((outer_flame, mid_flame, core_flame))
            # v2.1: Temperature-based lifetime
            temp_factor = (engine.T_cyl - 450.0) / 1800.0  # 0-1 based on temp
            fade_speed_adj = random.uniform(5.0, 12.0) * (1.0 - 0.3 * temp_factor)  # Slower fade at high temp
            flame_temp = random.uniform(1200.0, 2000.0) * (0.7 + 0.3 * temp_factor)
            particles.append(
                Particle(
                    x=RENDER.crank_x + random.uniform(-engine.B * RENDER.scale * 0.25, engine.B * RENDER.scale * 0.25),
                    y=random.uniform(chamber_top + 5, chamber_bottom),
                    color=flame_color,
                    vx=random.uniform(-8.0, 8.0) * (0.5 + burn_intensity),
                    vy=random.uniform(-1.0, 12.0) * (0.4 + pressure_intensity),
                    fade_speed=fade_speed_adj,
                    life=random.uniform(180.0, 255.0),
                    size=random.uniform(2.0, 4.0),
                    region="cylinder",
                    p_type="flame",
                    temperature=flame_temp
                )
            )
    if afterburn_intensity > 0.04 and state.dm_exh > 0:
        exh_y = cylinder_y + engine.x_exh * RENDER.scale + 10
        pop_count = reserve(1 + int(12 * afterburn_intensity))
        for _ in range(pop_count):
            exhaust_color = random.choice((outer_exhaust, mid_exhaust, core_exhaust))
            particles.append(
                Particle(
                    x=RENDER.crank_x + engine.B / 2 * RENDER.scale + random.uniform(6, 22),
                    y=exh_y + random.uniform(4, max(12, engine.w_exh * RENDER.scale - 4)),
                    color=exhaust_color,
                    vx=random.uniform(8.0, 18.0) * (0.55 + afterburn_intensity),
                    vy=random.uniform(-3.0, 3.0) * (0.5 + afterburn_intensity),
                    fade_speed=random.uniform(5.0, 10.0),
                    life=random.uniform(150.0, 255.0),
                    size=random.uniform(2.5, 4.5),
                    region="exhaust",
                    p_type="flame",
                    temperature=random.uniform(1000.0, 1500.0)
                )
            )
    if state.dm_tr > 0 and random.random() < state.dm_tr * 0.002 * 40000:
        crankcase_y = crankcase_top + random.uniform(20, 80)
        for _ in range(reserve(random.randint(1, 4))):
            is_fuel = random.random() < 0.3
            base_color = (50, 255, 100) if is_fuel else (200, 220, 255)
            # v2.1: Apply temperature-based color
            color = temp_based_color(base_color, engine.T_cyl)
            particle_temp = random.uniform(320.0, 450.0) if is_fuel else random.uniform(293.0, 350.0)
            particles.append(
                Particle(
                    x=RENDER.crank_x - engine.B / 2 * RENDER.scale - random.uniform(10, 35),
                    y=crankcase_y + random.uniform(-10, 10),
                    color=color,
                    vx=random.uniform(1.5, 6),
                    vy=random.uniform(-12, -5),
                    region="crankcase",
                    fade_speed=random.uniform(1.5, 4.0),
                    p_type="fuel" if is_fuel else "air",
                    temperature=particle_temp
                )
            )
    if state.dm_in > 0 and random.random() < state.dm_in * 0.002 * 20000:
        for _ in range(reserve(random.randint(1, 3))):
            is_fuel = random.random() < 0.3
            base_color = (50, 255, 100) if is_fuel else (200, 220, 255)
            # v2.1: Apply temperature-based color
            color = temp_based_color(base_color, engine.T_cyl)
            particle_temp = random.uniform(293.0, 350.0)
            particles.append(
                Particle(
                    x=RENDER.crank_x - engine.B / 2 * RENDER.scale - 50,
                    y=cylinder_y - random.uniform(20, 60),
                    color=color,
                    vx=random.uniform(2, 8),
                    vy=random.uniform(-5, -2),
                    region="intake",
                    fade_speed=random.uniform(2.0, 5.0),
                    p_type="fuel" if is_fuel else "air",
                    temperature=particle_temp
                )
            )


def update_particles(particles: list[Particle], state, engine, cylinder_y: float) -> list[Particle]:
    alive: list[Particle] = []
    
    # Get collision boundaries
    cyl_w = engine.B * RENDER.scale
    cyl_left = RENDER.crank_x - cyl_w / 2
    cyl_right = RENDER.crank_x + cyl_w / 2
    
    # Guard against zero A_p (piston area)
    piston_area = max(engine.A_p, 1e-9)
    clearance_height_px = engine.V_c / piston_area * RENDER.scale
    head_y = cylinder_y - 10
    piston_y = cylinder_y + clearance_height_px + state.x * RENDER.scale
    piston_bottom_y = piston_y + RENDER.piston_height_px
    
    exh_top = cylinder_y + engine.x_exh * RENDER.scale
    exh_bottom = exh_top + engine.w_exh * RENDER.scale
    
    tr_top = cylinder_y + engine.x_tr * RENDER.scale
    tr_bottom = tr_top + engine.w_tr * RENDER.scale
    
    crankcase_top = RENDER.crank_y - engine.R * RENDER.scale + 6
    crankcase_bottom = crankcase_top + engine.R * RENDER.scale * 1.95 + 70
    crankcase_left = RENDER.crank_x - cyl_w * 1.05
    crankcase_right = RENDER.crank_x + cyl_w * 1.05
    crankcase_centery = crankcase_top + (crankcase_bottom - crankcase_top) / 2
    
    intake_top = crankcase_centery - 18
    intake_bottom = crankcase_centery + 18
    
    transfer_left = cyl_left - 54

    for particle in particles:
        if not validate_particle(particle):
            continue

        particle.update(engine.T_cyl)
        
        if particle.region == "intake":
            if particle.x > crankcase_left:
                particle.region = "crankcase"
            else:
                if particle.y < intake_top:
                    particle.y = intake_top
                    particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                elif particle.y > intake_bottom:
                    particle.y = intake_bottom
                    particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                
                if particle.x < RENDER.crank_x - 150:
                    particle.x = RENDER.crank_x - 150
                    particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
            
            # Add lower boundary to prevent particles escaping further left
            if particle.x < RENDER.crank_x - 180:
                particle.x = RENDER.crank_x - 180
                particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
                    
                if state.dm_in > 0:
                    particle.vx += 0.5
                    
        elif particle.region == "crankcase":
            if state.dm_tr > 0:
                dx = (cyl_left - 20) - particle.x
                dy = tr_bottom - particle.y
                dist = math.hypot(dx, dy) + 1.0
                particle.vx += (dx / dist) * 2.0
                particle.vy += (dy / dist) * 2.0
                
            if particle.x < crankcase_left:
                particle.x = crankcase_left
                particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
            elif particle.x > crankcase_right:
                particle.x = crankcase_right
                particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
                
            if particle.y > crankcase_bottom:
                particle.y = crankcase_bottom
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                
            # Piston skirt boundary with height constant
            if particle.y < crankcase_top + RENDER.piston_height_px * 0.62:
                if particle.x > cyl_right:
                    particle.x = cyl_right
                    particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
                elif particle.x < cyl_left:
                    particle.region = "transfer"
                else:
                    if particle.y < piston_bottom_y:
                        particle.y = piston_bottom_y
                        particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                        # Piston velocity scale factor now defined as constant
                        piston_vel = engine.R * math.sin(engine.theta) * engine.omega * RENDER.scale * PISTON_VEL_SCALE
                        particle.vy += piston_vel * 0.08
            else:
                if cyl_left <= particle.x <= cyl_right:
                    if particle.y < piston_bottom_y:
                        particle.y = piston_bottom_y
                        particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                        piston_vel = engine.R * math.sin(engine.theta) * engine.omega * RENDER.scale * PISTON_VEL_SCALE
                        particle.vy += piston_vel * 0.08
                        
        elif particle.region == "transfer":
            if state.dm_tr > 0:
                if particle.y > tr_bottom:
                    particle.vy -= 2.5
                else:
                    particle.vy -= 1.5
                    particle.vx += 1.5
            elif state.dm_tr < 0:
                particle.vy += 1.5
                
            pad = particle.size * 1.5
            if particle.x < transfer_left + pad:
                particle.x = transfer_left + pad
                particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
            elif particle.x > cyl_left - pad:
                if tr_top <= particle.y <= tr_bottom and particle.y < piston_y:
                    if particle.x > cyl_left:
                        particle.region = "cylinder"
                else:
                    particle.x = cyl_left - pad
                    particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
                    
            if particle.y < tr_top - TRANSFER_PORT_TOP_OFFSET + pad:
                particle.y = tr_top - TRANSFER_PORT_TOP_OFFSET + pad
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                
            if particle.y > crankcase_top + 28:
                particle.region = "crankcase"
                
        elif particle.region == "cylinder":
            # Explosion push
            if engine.burn_fraction > 0.0 and engine.combustion_active and particle.p_type != "flame":
                dx = particle.x - RENDER.crank_x
                dy = particle.y - head_y
                dist = math.hypot(dx, dy) + 1.0
                push = engine.burn_fraction * 80.0 / dist
                particle.vx += (dx / dist) * push
                particle.vy += (dy / dist) * push
                if particle.p_type in ("fuel", "air"):
                    # Burn particles visually based on intensity
                    if random.random() < engine.burn_fraction * 0.3:
                        particle.p_type = "exhaust"
                        particle.color = (100, 100, 100)

            # Loop scavenging simulation with vorticity
            if state.dm_tr > 0 and particle.p_type != "flame":
                center_x = (cyl_left + cyl_right) / 2
                center_y = (head_y + piston_y) / 2
                rx = particle.x - center_x
                ry = particle.y - center_y
                dist = math.hypot(rx, ry) + 1.0
                
                # Primary swirl flow
                flow_strength = state.dm_tr * 250.0 / dist
                particle.vx += (-ry / dist) * flow_strength
                particle.vy += (rx / dist) * flow_strength
                
                # Secondary: transfer port jet with turbulent mixing
                if particle.y > tr_top and particle.y < tr_top + 40:
                    jet_strength = state.dm_tr * 0.15
                    particle.vx += jet_strength * (1.0 + random.uniform(-0.3, 0.3))
                    # Turbulent dispersion
                    particle.vy += random.uniform(-0.8, 0.8) * jet_strength
                    
            # Exhaust flow with expansion
            if state.dm_exh > 0 and particle.y > exh_top and particle.y < piston_y:
                dx = cyl_right + 10 - particle.x
                dy = (exh_top + exh_bottom) / 2 - particle.y
                dist = math.hypot(dx, dy) + 1.0
                pull = state.dm_exh * 200.0 / dist
                particle.vx += (dx / dist) * pull
                particle.vy += (dy / dist) * pull
                
                # Gas expansion near exhaust port
                if particle.x > cyl_right - 20:
                    expansion = state.dm_exh * 0.08
                    particle.vx += expansion * (1.0 + random.uniform(-0.2, 0.2))
                    
            # Reverse scavenging (exhaust port open during transfer)
            if state.dm_tr < 0 and particle.y > tr_top and particle.y < piston_y:
                dx = cyl_left - 10 - particle.x
                dy = (tr_top + tr_bottom) / 2 - particle.y
                dist = math.hypot(dx, dy) + 1.0
                pull = -state.dm_tr * 200.0 / dist
                particle.vx += (dx / dist) * pull
                particle.vy += (dy / dist) * pull
                
            # Turbulent mixing in cylinder during combustion
            if engine.combustion_active and engine.burn_fraction > 0.1:
                turbulence = engine.burn_fraction * 0.5
                particle.vx += random.uniform(-turbulence, turbulence)
                particle.vy += random.uniform(-turbulence, turbulence)

            pad = particle.size * 1.8
            if particle.x < cyl_left + pad:
                if tr_top <= particle.y <= tr_bottom and particle.y < piston_y:
                    if particle.x < cyl_left:
                        particle.region = "transfer"
                else:
                    particle.x = cyl_left + pad
                    particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
            elif particle.x > cyl_right - pad:
                if exh_top <= particle.y <= exh_bottom and particle.y < piston_y:
                    if particle.x > cyl_right:
                        particle.region = "exhaust"
                else:
                    particle.x = cyl_right - pad
                    particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
                    
            if particle.y < head_y + pad:
                particle.y = head_y + pad
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                
            if particle.y > piston_y - pad:
                particle.y = piston_y - pad
                if particle.vy > 0:
                    particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                # Use constant for piston velocity scale
                piston_vel = engine.R * math.sin(engine.theta) * engine.omega * RENDER.scale * PISTON_VEL_SCALE
                particle.vy += piston_vel * 0.1
                if particle.vy > 0:
                    particle.vy = max(0.0, particle.vy)
                
        elif particle.region == "exhaust":
            if state.dm_exh > 0:
                particle.vx += 1.5
            elif state.dm_exh < 0:
                particle.vx -= 1.5
                
            pad = particle.size * 1.5
            if particle.y < exh_top + pad:
                particle.y = exh_top + pad
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
            elif particle.y > exh_bottom - pad:
                particle.y = exh_bottom - pad
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
                
            if particle.x < cyl_right + pad:
                if exh_top <= particle.y <= exh_bottom and particle.y < piston_y:
                    if particle.x < cyl_right:
                        particle.region = "cylinder"
                else:
                    particle.x = cyl_right + pad
                    particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
            
            # Add upper boundary to prevent particles escaping to the right
            if particle.x > cyl_right + 150:
                particle.x = cyl_right + 150
                particle.vx *= -0.7 + random.uniform(-0.1, 0.1)
            
            # Add vertical boundaries to prevent particles escaping up/down
            if particle.y < exh_top - 30:
                particle.y = exh_top - 30
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)
            elif particle.y > exh_bottom + 30:
                particle.y = exh_bottom + 30
                particle.vy *= -0.7 + random.uniform(-0.1, 0.1)

        speed = math.hypot(particle.vx, particle.vy)
        if speed > 15.0:
            speed = max(speed, 1e-9)  # Prevent division by zero
            particle.vx = (particle.vx / speed) * 15.0
            particle.vy = (particle.vy / speed) * 15.0

        if particle.life > 0 and validate_particle(particle):
            alive.append(particle)
            
    return alive
