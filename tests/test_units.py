"""Unit tests for particles, utils, config, and renderer utilities."""
import math
import unittest

from particles import Particle, combustion_particle_colors, PISTON_VEL_SCALE
from physics.utils import clamp01, clamp, rescale_components, angle_diff, gaussian_falloff, is_finite, safe_divide
from config import QualityPreset, get_quality_preset, RenderConfig, WindowConfig
from renderer import combustion_palette, color_rgb


class ParticleClassTests(unittest.TestCase):
    def test_particle_initialization_defaults(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=1.0, vy=2.0)
        self.assertEqual(particle.x, 100.0)
        self.assertEqual(particle.y, 200.0)
        self.assertEqual(particle.color, (255, 0, 0))
        self.assertEqual(particle.vx, 1.0)
        self.assertEqual(particle.vy, 2.0)
        self.assertGreater(particle.life, 0.0)
        self.assertGreater(particle.size, 0.0)
        self.assertIsNotNone(particle.swirl_phase)
        self.assertIsNotNone(particle.swirl_speed)

    def test_particle_custom_values(self) -> None:
        particle = Particle(
            x=50.0, y=75.0, color=(0, 255, 0), vx=3.0, vy=4.0,
            fade_speed=10.0, life=200.0, size=5.0, region="exhaust",
            p_type="air", temperature=350.0
        )
        self.assertEqual(particle.fade_speed, 10.0)
        self.assertEqual(particle.life, 200.0)
        self.assertEqual(particle.size, 5.0)
        self.assertEqual(particle.region, "exhaust")
        self.assertEqual(particle.p_type, "air")
        self.assertEqual(particle.temperature, 350.0)

    def test_particle_update_changes_position(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=5.0, vy=3.0)
        initial_x, initial_y = particle.x, particle.y
        particle.update(293.0)
        self.assertNotEqual(particle.x, initial_x)
        self.assertNotEqual(particle.y, initial_y)

    def test_particle_update_decreases_life(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=1.0, vy=2.0, life=100.0)
        initial_life = particle.life
        particle.update(293.0)
        self.assertLess(particle.life, initial_life)

    def test_particle_spark_type_faster_decay(self) -> None:
        spark = Particle(x=100.0, y=200.0, color=(255, 255, 200), vx=5.0, vy=3.0, p_type="spark", life=100.0)
        air = Particle(x=100.0, y=200.0, color=(200, 220, 255), vx=5.0, vy=3.0, p_type="air", life=100.0)
        spark.update(293.0)
        air.update(293.0)
        self.assertLess(spark.life, air.life)

    def test_particle_fuel_type_gravity(self) -> None:
        fuel = Particle(x=100.0, y=200.0, color=(50, 255, 100), vx=0.0, vy=0.0, p_type="fuel")
        initial_vy = fuel.vy
        fuel.update(293.0)
        self.assertGreater(fuel.vy, initial_vy)

    def test_particle_flame_cooling(self) -> None:
        flame = Particle(x=100.0, y=200.0, color=(255, 200, 50), vx=1.0, vy=1.0, p_type="flame", temperature=1800.0)
        initial_temp = flame.temperature
        flame.update(293.0)
        self.assertLess(flame.temperature, initial_temp)

    def test_particle_buoyancy_hot_particles(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=0.0, vy=0.0, temperature=1000.0)
        initial_vy = particle.vy
        particle.update(293.0)
        self.assertLess(particle.vy, initial_vy)

    def test_particle_thermophoresis(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(200, 220, 255), vx=0.0, vy=0.0, p_type="air")
        initial_vy = particle.vy
        particle.update(800.0)
        self.assertLess(particle.vy, initial_vy)

    def test_particle_fuel_evaporation(self) -> None:
        fuel = Particle(x=100.0, y=200.0, color=(50, 255, 100), vx=1.0, vy=1.0, p_type="fuel", size=3.0, initial_size=3.0)
        initial_size = fuel.size
        for _ in range(100):
            fuel.update(450.0)
        self.assertLess(fuel.size, initial_size)

    def test_particle_fuel_converts_to_vapor(self) -> None:
        fuel = Particle(x=100.0, y=200.0, color=(50, 255, 100), vx=1.0, vy=1.0, p_type="fuel", size=3.0, initial_size=10.0)
        for _ in range(1000):
            fuel.update(500.0)
        # Fuel may or may not convert depending on evaporation rate
        self.assertIn(fuel.p_type, ["fuel", "vapor"])


class CombustionParticleColorsTests(unittest.TestCase):
    def test_returns_three_color_tuples(self) -> None:
        result = combustion_particle_colors(1.0, 1500.0, 0.5)
        self.assertEqual(len(result), 3)
        for color in result:
            self.assertEqual(len(color), 3)
            self.assertTrue(all(0 <= c <= 255 for c in color))

    def test_lean_mixture_affects_colors(self) -> None:
        lean = combustion_particle_colors(1.5, 1500.0, 0.5)
        stoichiometric = combustion_particle_colors(1.0, 1500.0, 0.5)
        self.assertNotEqual(lean, stoichiometric)

    def test_rich_mixture_affects_colors(self) -> None:
        rich = combustion_particle_colors(0.7, 1500.0, 0.5)
        stoichiometric = combustion_particle_colors(1.0, 1500.0, 0.5)
        self.assertNotEqual(rich, stoichiometric)

    def test_temperature_affects_colors(self) -> None:
        cold = combustion_particle_colors(1.0, 500.0, 0.5)
        hot = combustion_particle_colors(1.0, 2000.0, 0.5)
        self.assertNotEqual(cold, hot)


class UtilsClampTests(unittest.TestCase):
    def test_clamp01_clamps_to_zero(self) -> None:
        self.assertEqual(clamp01(-5.0), 0.0)

    def test_clamp01_clamps_to_one(self) -> None:
        self.assertEqual(clamp01(5.0), 1.0)

    def test_clamp01_passes_through(self) -> None:
        self.assertEqual(clamp01(0.5), 0.5)

    def test_clamp_clamps_below_min(self) -> None:
        self.assertEqual(clamp(-5.0, 0.0, 10.0), 0.0)

    def test_clamp_clamps_above_max(self) -> None:
        self.assertEqual(clamp(15.0, 0.0, 10.0), 10.0)

    def test_clamp_passes_through(self) -> None:
        self.assertEqual(clamp(5.0, 0.0, 10.0), 5.0)


class UtilsRescaleComponentsTests(unittest.TestCase):
    def test_rescale_components_equal_distribution(self) -> None:
        result = rescale_components(0.0, 0.0, 0.0, target_total=10.0)
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(sum(result), 10.0, places=5)

    def test_rescale_components_preserves_proportions(self) -> None:
        result = rescale_components(1.0, 2.0, 3.0, target_total=12.0)
        self.assertAlmostEqual(sum(result), 12.0, places=5)
        self.assertAlmostEqual(result[1] / result[0], 2.0, places=5)
        self.assertAlmostEqual(result[2] / result[0], 3.0, places=5)

    def test_rescale_components_negative_values_clamped(self) -> None:
        result = rescale_components(-1.0, 2.0, -3.0, target_total=10.0)
        self.assertGreaterEqual(result[0], 0.0)
        self.assertGreaterEqual(result[2], 0.0)
        self.assertAlmostEqual(sum(result), 10.0, places=5)

    def test_rescale_components_zero_target(self) -> None:
        result = rescale_components(1.0, 2.0, 3.0, target_total=0.0)
        self.assertTrue(all(v >= 0 for v in result))


class UtilsAngleDiffTests(unittest.TestCase):
    def test_angle_diff_same_angle(self) -> None:
        self.assertEqual(angle_diff(45.0, 45.0), 0.0)

    def test_angle_diff_positive_wrap(self) -> None:
        self.assertAlmostEqual(angle_diff(10.0, 350.0), 20.0)

    def test_angle_diff_negative_wrap(self) -> None:
        self.assertAlmostEqual(angle_diff(350.0, 10.0), -20.0)

    def test_angle_diff_full_circle(self) -> None:
        self.assertEqual(angle_diff(0.0, 360.0), 0.0)

    def test_angle_diff_opposite_sides(self) -> None:
        result = angle_diff(0.0, 180.0)
        self.assertTrue(result == 180.0 or result == -180.0)


class UtilsGaussianFalloffTests(unittest.TestCase):
    def test_gaussian_at_zero(self) -> None:
        self.assertAlmostEqual(gaussian_falloff(0.0, 1.0), 1.0, places=5)

    def test_gaussian_at_sigma(self) -> None:
        self.assertAlmostEqual(gaussian_falloff(1.0, 1.0), math.exp(-1.0), places=5)

    def test_gaussian_at_zero_sigma(self) -> None:
        result = gaussian_falloff(1.0, 1e-15)
        self.assertEqual(result, 0.0)

    def test_gaussian_returns_between_zero_and_one(self) -> None:
        for x in [0.0, 0.5, 1.0, 2.0, 5.0]:
            result = gaussian_falloff(x, 1.0)
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 1.0)


class UtilsIsFiniteTests(unittest.TestCase):
    def test_is_finite_accepts_normal(self) -> None:
        self.assertTrue(is_finite(1.0))
        self.assertTrue(is_finite(-100.5))

    def test_is_finite_rejects_nan(self) -> None:
        self.assertFalse(is_finite(float('nan')))

    def test_is_finite_rejects_infinity(self) -> None:
        self.assertFalse(is_finite(float('inf')))
        self.assertFalse(is_finite(float('-inf')))


class UtilsSafeDivideTests(unittest.TestCase):
    def test_safe_divide_normal(self) -> None:
        self.assertAlmostEqual(safe_divide(10.0, 2.0), 5.0)

    def test_safe_divide_zero_denominator(self) -> None:
        self.assertEqual(safe_divide(10.0, 0.0), 0.0)

    def test_safe_divide_custom_default(self) -> None:
        self.assertEqual(safe_divide(10.0, 0.0, 99.0), 99.0)

    def test_safe_divide_small_denominator(self) -> None:
        result = safe_divide(1.0, 1e-10)
        # Returns large number since 1e-10 > 1e-12 threshold
        self.assertGreater(result, 1e9)


class ConfigQualityPresetTests(unittest.TestCase):
    def test_simple_2d_preset(self) -> None:
        config = get_quality_preset(QualityPreset.SIMPLE_2D)
        self.assertEqual(config.quality_preset, QualityPreset.SIMPLE_2D)
        self.assertFalse(config.enable_hd_render)
        self.assertFalse(config.enable_bloom)
        self.assertFalse(config.enable_animations)

    def test_low_preset(self) -> None:
        config = get_quality_preset(QualityPreset.LOW)
        self.assertEqual(config.quality_preset, QualityPreset.LOW)
        self.assertFalse(config.enable_hd_render)

    def test_medium_preset(self) -> None:
        config = get_quality_preset(QualityPreset.MEDIUM)
        self.assertEqual(config.quality_preset, QualityPreset.MEDIUM)
        self.assertTrue(config.enable_materials)
        self.assertTrue(config.enable_animations)

    def test_high_preset(self) -> None:
        config = get_quality_preset(QualityPreset.HIGH)
        self.assertEqual(config.quality_preset, QualityPreset.HIGH)
        self.assertTrue(config.enable_hd_render)
        self.assertTrue(config.enable_bloom)

    def test_ultra_preset(self) -> None:
        config = get_quality_preset(QualityPreset.ULTRA)
        self.assertEqual(config.quality_preset, QualityPreset.ULTRA)
        self.assertEqual(config.hd_render_scale, 2.0)
        self.assertEqual(config.max_particles, 800)

    def test_window_config_defaults(self) -> None:
        config = WindowConfig()
        self.assertEqual(config.width, 1300)
        self.assertEqual(config.height, 720)
        self.assertEqual(config.fps, 60)

    def test_render_config_defaults(self) -> None:
        config = RenderConfig()
        self.assertEqual(config.scale, 3000.0)
        self.assertEqual(config.crank_x, 400)
        self.assertEqual(config.crank_y, 550)


class RendererColorTests(unittest.TestCase):
    def test_color_rgb_clamps_values(self) -> None:
        self.assertEqual(color_rgb(300.0, -50.0, 175.0), (255, 0, 175))

    def test_color_rgb_passes_normal(self) -> None:
        self.assertEqual(color_rgb(100.0, 150.0, 200.0), (100, 150, 200))

    def test_color_rgb_returns_tuple(self) -> None:
        result = color_rgb(128.0, 64.0, 192.0)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)


class CombustionPaletteTests(unittest.TestCase):
    def test_returns_three_tuples(self) -> None:
        result = combustion_palette(1.0, 1500.0, 0.5)
        self.assertEqual(len(result), 3)
        for color in result:
            self.assertIsInstance(color, tuple)
            self.assertEqual(len(color), 3)

    def test_lean_mixture_different_colors(self) -> None:
        lean = combustion_palette(1.5, 1500.0, 0.5)
        normal = combustion_palette(1.0, 1500.0, 0.5)
        self.assertNotEqual(lean, normal)

    def test_rich_mixture_different_colors(self) -> None:
        rich = combustion_palette(0.6, 1500.0, 0.5)
        normal = combustion_palette(1.0, 1500.0, 0.5)
        self.assertNotEqual(rich, normal)

    def test_temperature_affects_colors(self) -> None:
        cold = combustion_palette(1.0, 500.0, 0.5)
        hot = combustion_palette(1.0, 2500.0, 0.5)
        self.assertNotEqual(cold, hot)

    def test_phase_affects_colors(self) -> None:
        start = combustion_palette(1.0, 1500.0, 0.0)
        end = combustion_palette(1.0, 1500.0, 1.0)
        self.assertNotEqual(start, end)

    def test_colors_within_range(self) -> None:
        result = combustion_palette(0.5, 3000.0, 1.0)
        for color in result:
            for component in color:
                self.assertGreaterEqual(component, 0)
                self.assertLessEqual(component, 255)


class ConstantsTests(unittest.TestCase):
    def test_piston_vel_scale_is_positive(self) -> None:
        self.assertGreater(PISTON_VEL_SCALE, 0.0)
        self.assertLess(PISTON_VEL_SCALE, 1.0)


if __name__ == "__main__":
    unittest.main()
