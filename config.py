from dataclasses import dataclass
from enum import Enum
import json
import os


class QualityPreset(Enum):
    """Rendering quality presets for different hardware capabilities."""
    SIMPLE_2D = "simple_2d"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


@dataclass(frozen=True)
class WindowConfig:
    width: int = 1300
    height: int = 720
    fps: int = 60
    title: str = "Realistisk 2-taktsmotor - Exakt Termodynamik & Gasdynamik"


@dataclass(frozen=True)
class RenderConfig:
    background_color: tuple[int, int, int] = (15, 15, 25)
    cylinder_color: tuple[int, int, int, int] = (180, 180, 210, 100)
    piston_color: tuple[int, int, int] = (120, 120, 140)
    scale: float = 3000.0
    crank_x: int = 400
    crank_y: int = 550
    # Engine geometry constants (pixels)
    piston_height_px: float = 45.0
    
    # v2.1 Rendering quality settings
    quality_preset: QualityPreset = QualityPreset.MEDIUM
    
    # HD rendering
    hd_render_scale: float = 1.0  # 1.0 = native, 1.5 = 1.5x, 2.0 = 2x resolution
    enable_hd_render: bool = True
    
    # Bloom settings (requires HIGH/ULTRA preset for performance)
    enable_bloom: bool = False  # Disabled by default due to CPU-bound performance
    bloom_threshold: float = 0.7
    bloom_intensity: float = 1.0
    bloom_sigma: float = 4.0
    bloom_quality: int = 2  # 1=fast, 2=medium, 3=high
    
    # Particle settings
    max_particles: int = 500
    particle_lod_distance: float = 200.0  # Distance at which LOD kicks in
    enable_particle_glow: bool = True
    
    # Material settings
    enable_materials: bool = True
    material_texture_size: int = 256  # Texture resolution
    
    # Animation settings
    enable_animations: bool = True
    enable_vibration: bool = True
    enable_screen_shake: bool = True
    enable_heat_effects: bool = True
    
    # Dashboard settings
    enable_dashboard: bool = True
    gauge_update_rate: int = 30  # Hz, lower than physics for performance


def get_quality_preset(preset: QualityPreset) -> RenderConfig:
    """Get RenderConfig with quality preset applied."""
    base_config = RenderConfig()
    
    if preset == QualityPreset.SIMPLE_2D:
        return RenderConfig(
            quality_preset=QualityPreset.SIMPLE_2D,
            hd_render_scale=1.0,
            enable_hd_render=False,
            enable_bloom=False,
            max_particles=150,
            enable_particle_glow=False,
            enable_materials=False,
            enable_animations=False,
            enable_vibration=False,
            enable_screen_shake=False,
            enable_heat_effects=False,
            enable_dashboard=True,
            gauge_update_rate=20,
        )
    
    if preset == QualityPreset.LOW:
        return RenderConfig(
            quality_preset=QualityPreset.LOW,
            hd_render_scale=1.0,
            enable_hd_render=False,
            enable_bloom=False,
            max_particles=200,
            enable_particle_glow=False,
            enable_materials=False,
            enable_animations=False,
            enable_vibration=False,
            enable_screen_shake=False,
            enable_heat_effects=False,
            enable_dashboard=True,
            gauge_update_rate=15,
        )
    
    elif preset == QualityPreset.MEDIUM:
        return RenderConfig(
            quality_preset=QualityPreset.MEDIUM,
            hd_render_scale=1.0,
            enable_hd_render=False,
            enable_bloom=False,  # Disabled due to performance - pixel-by-pixel too slow
            bloom_quality=1,
            bloom_intensity=0.7,
            max_particles=300,
            enable_particle_glow=True,
            enable_materials=True,
            material_texture_size=128,
            enable_animations=True,
            enable_vibration=True,
            enable_screen_shake=False,
            enable_heat_effects=False,
            enable_dashboard=True,
            gauge_update_rate=30,
        )
    
    elif preset == QualityPreset.HIGH:
        return RenderConfig(
            quality_preset=QualityPreset.HIGH,
            hd_render_scale=1.5,
            enable_hd_render=True,
            enable_bloom=True,
            bloom_quality=2,
            bloom_intensity=1.0,
            max_particles=500,
            enable_particle_glow=True,
            enable_materials=True,
            material_texture_size=256,
            enable_animations=True,
            enable_vibration=True,
            enable_screen_shake=True,
            enable_heat_effects=True,
            enable_dashboard=True,
            gauge_update_rate=30,
        )
    
    elif preset == QualityPreset.ULTRA:
        return RenderConfig(
            quality_preset=QualityPreset.ULTRA,
            hd_render_scale=2.0,
            enable_hd_render=True,
            enable_bloom=True,
            bloom_quality=3,
            bloom_intensity=1.2,
            bloom_sigma=5.0,
            max_particles=800,
            enable_particle_glow=True,
            enable_materials=True,
            material_texture_size=512,
            enable_animations=True,
            enable_vibration=True,
            enable_screen_shake=True,
            enable_heat_effects=True,
            enable_dashboard=True,
            gauge_update_rate=60,
        )
    
    return base_config


WINDOW = WindowConfig()
RENDER = get_quality_preset(QualityPreset.SIMPLE_2D)


class TuningPreset(Enum):
    """Tuning presets för mopedtrimning."""
    STOCK = "stock"
    GATTRIM = "gattrim"
    RACING = "racing"
    CLASSIC = "classic"
    DRAGRACE = "dragrace"
    CUSTOM = "custom"


TUNING_PRESETS = {
    TuningPreset.STOCK: {
        "name": "Stock",
        "description": "Standardinställningar - originalmoped",
        "stroke_multiplier": 1.0,
        "bore_multiplier": 1.0,
        "compression_ratio": 7.5,
        "rod_length": 0.095,
        "transfer_port_height": 0.034,
        "exhaust_port_height": 0.024,
        "exhaust_port_width": 0.038,
        "transfer_port_width": 0.032,
        "pipe_resonance_freq": 140.0,
        "pipe_length": 1.0,
        "pipe_q_factor": 2.5,
        "burn_duration_factor": 1.0,
        "combustion_efficiency": 1.0,
        "fuel_evap_rate_cr": 1.0,
        "fuel_evap_rate_cyl": 1.0,
        "reed_stiffness": 1200.0,
        "inertia_multiplier": 1.0,
        "friction_factor": 1.0,
        "mechanical_efficiency": 0.85,
    },
    TuningPreset.GATTRIM: {
        "name": "Gattrim",
        "description": "Optimerad för pålitlighet - gata",
        "stroke_multiplier": 1.0,
        "bore_multiplier": 1.0,
        "compression_ratio": 8.0,
        "rod_length": 0.095,
        "transfer_port_height": 0.032,
        "exhaust_port_height": 0.022,
        "exhaust_port_width": 0.036,
        "transfer_port_width": 0.030,
        "pipe_resonance_freq": 120.0,
        "pipe_length": 1.1,
        "pipe_q_factor": 2.8,
        "burn_duration_factor": 1.0,
        "combustion_efficiency": 0.95,
        "fuel_evap_rate_cr": 1.2,
        "fuel_evap_rate_cyl": 1.1,
        "reed_stiffness": 1400.0,
        "inertia_multiplier": 1.1,
        "friction_factor": 1.0,
        "mechanical_efficiency": 0.82,
    },
    TuningPreset.RACING: {
        "name": "Racing",
        "description": "Hög effekt - tävlingsinställning",
        "stroke_multiplier": 1.05,
        "bore_multiplier": 1.08,
        "compression_ratio": 9.5,
        "rod_length": 0.090,
        "transfer_port_height": 0.038,
        "exhaust_port_height": 0.028,
        "exhaust_port_width": 0.042,
        "transfer_port_width": 0.036,
        "pipe_resonance_freq": 160.0,
        "pipe_length": 0.9,
        "pipe_q_factor": 2.2,
        "burn_duration_factor": 0.85,
        "combustion_efficiency": 1.0,
        "fuel_evap_rate_cr": 1.5,
        "fuel_evap_rate_cyl": 1.3,
        "reed_stiffness": 1000.0,
        "inertia_multiplier": 0.8,
        "friction_factor": 0.9,
        "mechanical_efficiency": 0.88,
    },
    TuningPreset.CLASSIC: {
        "name": "Classic",
        "description": "70-tals mopedstil - mjuk och varm",
        "stroke_multiplier": 0.95,
        "bore_multiplier": 1.0,
        "compression_ratio": 7.0,
        "rod_length": 0.100,
        "transfer_port_height": 0.030,
        "exhaust_port_height": 0.020,
        "exhaust_port_width": 0.034,
        "transfer_port_width": 0.028,
        "pipe_resonance_freq": 100.0,
        "pipe_length": 1.2,
        "pipe_q_factor": 3.0,
        "burn_duration_factor": 1.2,
        "combustion_efficiency": 0.9,
        "fuel_evap_rate_cr": 0.8,
        "fuel_evap_rate_cyl": 0.8,
        "reed_stiffness": 1600.0,
        "inertia_multiplier": 1.3,
        "friction_factor": 1.1,
        "mechanical_efficiency": 0.80,
    },
    TuningPreset.DRAGRACE: {
        "name": "Dragrace",
        "description": "Max acceleration - korta distanser",
        "stroke_multiplier": 1.1,
        "bore_multiplier": 1.12,
        "compression_ratio": 10.0,
        "rod_length": 0.085,
        "transfer_port_height": 0.040,
        "exhaust_port_height": 0.030,
        "exhaust_port_width": 0.045,
        "transfer_port_width": 0.038,
        "pipe_resonance_freq": 180.0,
        "pipe_length": 0.8,
        "pipe_q_factor": 2.0,
        "burn_duration_factor": 0.75,
        "combustion_efficiency": 1.0,
        "fuel_evap_rate_cr": 1.8,
        "fuel_evap_rate_cyl": 1.5,
        "reed_stiffness": 900.0,
        "inertia_multiplier": 0.65,
        "friction_factor": 0.8,
        "mechanical_efficiency": 0.90,
    },
}


def get_tuning_preset(preset: TuningPreset) -> dict:
    """Hämta inställningar för en tuning preset."""
    if preset == TuningPreset.CUSTOM:
        return TUNING_PRESETS[TuningPreset.STOCK].copy()
    return TUNING_PRESETS.get(preset, TUNING_PRESETS[TuningPreset.STOCK]).copy()


def apply_tuning_preset(engine, preset: TuningPreset) -> None:
    """Applicera en tuning preset på en motor."""
    settings = get_tuning_preset(preset)
    engine.stroke_multiplier = settings["stroke_multiplier"]
    engine.bore_multiplier = settings["bore_multiplier"]
    engine.compression_ratio = settings["compression_ratio"]
    engine.rod_length = settings["rod_length"]
    engine.transfer_port_height = settings["transfer_port_height"]
    engine.exhaust_port_height = settings["exhaust_port_height"]
    engine.exhaust_port_width = settings["exhaust_port_width"]
    engine.transfer_port_width = settings["transfer_port_width"]
    engine.pipe_resonance_freq = settings["pipe_resonance_freq"]
    engine.pipe_length = settings["pipe_length"]
    engine.pipe_q_factor = settings["pipe_q_factor"]
    engine.burn_duration_factor = settings["burn_duration_factor"]
    engine.combustion_efficiency = settings["combustion_efficiency"]
    engine.fuel_evap_rate_cr = settings["fuel_evap_rate_cr"]
    engine.fuel_evap_rate_cyl = settings["fuel_evap_rate_cyl"]
    engine.reed_stiffness = settings["reed_stiffness"]
    engine.inertia_multiplier = settings["inertia_multiplier"]
    engine.friction_factor = settings["friction_factor"]
    engine.mechanical_efficiency = settings["mechanical_efficiency"]


def save_tuning_preset(engine, name: str, filepath: str = None) -> str:
    """Spara nuvarande motorinställningar till fil."""
    if filepath is None:
        user_dir = os.path.expanduser("~")
        twostroke_dir = os.path.join(user_dir, ".twostroke")
        os.makedirs(twostroke_dir, exist_ok=True)
        filepath = os.path.join(twostroke_dir, f"{name}.json")
    
    settings = {
        "name": name,
        "stroke_multiplier": engine.stroke_multiplier,
        "bore_multiplier": engine.bore_multiplier,
        "compression_ratio": engine.compression_ratio,
        "rod_length": engine.rod_length,
        "transfer_port_height": engine.transfer_port_height,
        "exhaust_port_height": engine.exhaust_port_height,
        "exhaust_port_width": engine.exhaust_port_width,
        "transfer_port_width": engine.transfer_port_width,
        "pipe_resonance_freq": engine.pipe_resonance_freq,
        "pipe_length": engine.pipe_length,
        "pipe_q_factor": engine.pipe_q_factor,
        "burn_duration_factor": engine.burn_duration_factor,
        "combustion_efficiency": engine.combustion_efficiency,
        "fuel_evap_rate_cr": engine.fuel_evap_rate_cr,
        "fuel_evap_rate_cyl": engine.fuel_evap_rate_cyl,
        "reed_stiffness": engine.reed_stiffness,
        "inertia_multiplier": engine.inertia_multiplier,
        "friction_factor": engine.friction_factor,
        "mechanical_efficiency": engine.mechanical_efficiency,
    }
    
    with open(filepath, 'w') as f:
        json.dump(settings, f, indent=2)
    return filepath


def load_tuning_preset(engine, filepath: str) -> bool:
    """Ladda motorinställningar från fil."""
    try:
        with open(filepath, 'r') as f:
            settings = json.load(f)
        
        engine.stroke_multiplier = settings.get("stroke_multiplier", 1.0)
        engine.bore_multiplier = settings.get("bore_multiplier", 1.0)
        engine.compression_ratio = settings.get("compression_ratio", 7.5)
        engine.rod_length = settings.get("rod_length", 0.095)
        engine.transfer_port_height = settings.get("transfer_port_height", 0.034)
        engine.exhaust_port_height = settings.get("exhaust_port_height", 0.024)
        engine.exhaust_port_width = settings.get("exhaust_port_width", 0.038)
        engine.transfer_port_width = settings.get("transfer_port_width", 0.032)
        engine.pipe_resonance_freq = settings.get("pipe_resonance_freq", 140.0)
        engine.pipe_length = settings.get("pipe_length", 1.0)
        engine.pipe_q_factor = settings.get("pipe_q_factor", 2.5)
        engine.burn_duration_factor = settings.get("burn_duration_factor", 1.0)
        engine.combustion_efficiency = settings.get("combustion_efficiency", 1.0)
        engine.fuel_evap_rate_cr = settings.get("fuel_evap_rate_cr", 1.0)
        engine.fuel_evap_rate_cyl = settings.get("fuel_evap_rate_cyl", 1.0)
        engine.reed_stiffness = settings.get("reed_stiffness", 1200.0)
        engine.inertia_multiplier = settings.get("inertia_multiplier", 1.0)
        engine.friction_factor = settings.get("friction_factor", 1.0)
        engine.mechanical_efficiency = settings.get("mechanical_efficiency", 0.85)
        return True
    except Exception as e:
        print(f"Error loading preset: {e}")
        return False
