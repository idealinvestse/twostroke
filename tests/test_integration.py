"""
Integration test for long-running engine stability.
This test runs the engine for an extended duration to check for numerical drift and stability.
"""
import unittest

import config as config_module
import particles as particles_module
import renderer as renderer_module
from app import apply_render_config
from physics import EnginePhysics


class LongRunningStabilityTests(unittest.TestCase):
    def test_render_config_propagates_to_cached_module_references(self) -> None:
        original_config = config_module.RENDER
        try:
            new_config = config_module.get_quality_preset(config_module.QualityPreset.HIGH)
            apply_render_config(new_config)

            self.assertIs(config_module.RENDER, new_config)
            self.assertIs(particles_module.RENDER, new_config)
            self.assertIs(renderer_module.RENDER, new_config)
        finally:
            apply_render_config(original_config)

    def test_extended_run_stability(self) -> None:
        """Run engine for equivalent of 30 seconds to check for numerical stability."""
        engine = EnginePhysics()
        engine.throttle = 0.7
        engine.fuel_ratio = 0.068
        
        # Run for 30 seconds at 600 Hz (18000 steps)
        dt = 1 / 600
        steps = 18000
        
        for i in range(steps):
            try:
                snapshot = engine.step(dt)
                # Validate state after each step
                self.assertTrue(engine.validate_state(), f"State validation failed at step {i}")
                
                # Check for reasonable values
                self.assertGreater(snapshot.p_cyl, 0, f"Invalid cylinder pressure at step {i}")
                self.assertGreater(snapshot.p_cr, 0, f"Invalid crankcase pressure at step {i}")
                self.assertLess(snapshot.p_cyl, 10_000_000, f"Cylinder pressure too high at step {i}")
                self.assertLess(snapshot.p_cr, 500_000, f"Crankcase pressure too high at step {i}")
                
            except RuntimeError as e:
                self.fail(f"Engine step failed at step {i}: {e}")
        
        # After extended run, check final state is still valid
        self.assertTrue(engine.validate_state())
        self.assertGreater(engine.omega, 0)
        self.assertLess(engine.omega, 2000)  # Should not exceed max reasonable RPM

    def test_parameter_extremes_stability(self) -> None:
        """Test engine stability with extreme parameter combinations."""
        test_configs = [
            (0.0, 0.02),   # Minimum throttle, lean mixture
            (1.0, 0.15),   # Maximum throttle, rich mixture
            (0.5, 0.068),  # Mid-range values
        ]
        
        for throttle, fuel_ratio in test_configs:
            with self.subTest(throttle=throttle, fuel_ratio=fuel_ratio):
                engine = EnginePhysics()
                engine.throttle = throttle
                engine.fuel_ratio = fuel_ratio
                
                # Run for 5 seconds
                dt = 1 / 600
                for i in range(3000):
                    engine.step(dt)
                    self.assertTrue(engine.validate_state(), f"Failed at step {i} with throttle={throttle}, fuel_ratio={fuel_ratio}")

    def test_ignition_timing_extremes(self) -> None:
        """Test engine with extreme ignition timing values."""
        for ignition_angle in [300, 340, 355]:
            with self.subTest(ignition_angle=ignition_angle):
                engine = EnginePhysics()
                engine.throttle = 0.7
                engine.fuel_ratio = 0.068
                engine.ignition_angle_deg = ignition_angle
                
                # Run for 3 seconds
                dt = 1 / 600
                for i in range(1800):
                    engine.step(dt)
                    self.assertTrue(engine.validate_state(), f"Failed at step {i} with ignition_angle={ignition_angle}")


if __name__ == "__main__":
    unittest.main()
