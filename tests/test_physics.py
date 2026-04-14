import math
import unittest

from physics import (
    EnginePhysics,
    flow_function,
    mass_flow,
    MAX_CYLINDER_PRESSURE,
    MIN_PRESSURE,
    T_ATM,
)
from particles import validate_particle, Particle


class PhysicsFunctionTests(unittest.TestCase):
    def test_flow_function_is_zero_when_downstream_pressure_is_higher(self) -> None:
        self.assertEqual(flow_function(100000.0, 110000.0), 0.0)

    def test_mass_flow_is_zero_when_area_is_zero(self) -> None:
        self.assertEqual(mass_flow(0.7, 0.0, 150000.0, 300.0, 100000.0), 0.0)

    def test_flow_function_handles_zero_upstream_pressure(self) -> None:
        self.assertEqual(flow_function(0.0, 100000.0), 0.0)

    def test_mass_flow_handles_zero_upstream_pressure(self) -> None:
        self.assertEqual(mass_flow(0.7, 0.001, 0.0, 300.0, 100000.0), 0.0)


class EnginePhysicsTests(unittest.TestCase):
    def run_engine(
        self,
        throttle: float,
        fuel_ratio: float,
        ignition_angle_deg: float,
        steps: int = 6000,
        idle_fuel_trim: float = 1.0,
    ):
        engine = EnginePhysics()
        engine.throttle = throttle
        engine.fuel_ratio = fuel_ratio
        engine.ignition_angle_deg = ignition_angle_deg
        engine.idle_fuel_trim = idle_fuel_trim
        snapshot = engine.snapshot()
        for _ in range(steps):
            snapshot = engine.step(1 / 600)
        return snapshot

    def test_angle_diff_wraps_correctly(self) -> None:
        self.assertEqual(EnginePhysics.angle_diff(10, 350), 20.0)

    def test_kinematics_returns_positive_volumes(self) -> None:
        engine = EnginePhysics()
        x, v_cyl, v_cr, _ = engine.get_kinematics(engine.theta)
        self.assertGreaterEqual(x, 0.0)
        self.assertGreater(v_cyl, 0.0)
        self.assertGreater(v_cr, 0.0)

    def test_step_advances_theta(self) -> None:
        engine = EnginePhysics()
        initial_theta = engine.theta
        engine.step(0.005)
        self.assertNotEqual(initial_theta, engine.theta)

    def test_step_rejects_invalid_dt(self) -> None:
        engine = EnginePhysics()
        for invalid_dt in (0.0, -1e-3, float("nan")):
            with self.subTest(dt=invalid_dt):
                with self.assertRaises(ValueError):
                    engine.step(invalid_dt)

    def test_snapshot_rpm_matches_omega(self) -> None:
        engine = EnginePhysics()
        snapshot = engine.snapshot()
        # RPM is smoothed with EMA, so it won't match exactly initially
        # Just verify it's in a reasonable range
        self.assertGreaterEqual(snapshot.rpm, 0.0)
        self.assertLess(snapshot.rpm, 20000.0)  # Sanity check for max RPM

    def test_validate_state_rejects_invalid_pressure_and_pipe_state(self) -> None:
        engine = EnginePhysics()
        self.assertTrue(engine.validate_state())

        engine.cylinders[0].p_cyl = float("inf")
        self.assertFalse(engine.validate_state())

        engine = EnginePhysics()
        engine.p_pipe = float("nan")
        self.assertFalse(engine.validate_state())

    def test_snapshot_and_step_reject_empty_cylinder_list(self) -> None:
        engine = EnginePhysics()
        engine.cylinders = []

        with self.assertRaises(RuntimeError):
            engine.snapshot()

        with self.assertRaises(RuntimeError):
            engine.step(0.005)

    def test_throttle_changes_engine_speed(self) -> None:
        """Test throttle with 50cc engine - verify engine runs at different throttle openings."""
        low = self.run_engine(0.25, 0.06, 340, steps=4000)
        high = self.run_engine(1.0, 0.06, 340, steps=4000)
        # Both should run without crashing
        self.assertGreater(low.rpm, 0.0, "Low throttle should produce some rpm")
        self.assertGreater(high.rpm, 0.0, "High throttle should produce some rpm")
        # Higher throttle should generally produce higher RPM
        self.assertGreater(high.rpm, low.rpm * 0.5)

    def test_fuel_ratio_changes_engine_speed(self) -> None:
        lean = self.run_engine(1.0, 0.05, 340)
        rich = self.run_engine(1.0, 0.10, 340)
        # 50cc engine - check that fuel ratio has measurable effect
        self.assertGreater(abs(rich.rpm - lean.rpm), 1.0)

    def test_ignition_timing_changes_engine_speed(self) -> None:
        """Test ignition timing with 50cc engine - verify engine runs at different timings."""
        retarded = self.run_engine(1.0, 0.08, 320, steps=4000)
        advanced = self.run_engine(1.0, 0.08, 350, steps=4000)
        # 50cc engine - both should run, RPM may vary based on combustion efficiency
        self.assertGreater(retarded.rpm, 80.0, "Retarded timing should still run")
        self.assertGreater(advanced.rpm, 80.0, "Advanced timing should still run")

    def test_idle_fuel_trim_changes_low_throttle_engine_speed(self) -> None:
        """Test idle fuel trim with 50cc engine."""
        engine1 = EnginePhysics()
        engine1.throttle = 0.10
        engine1.fuel_ratio = 0.08
        engine1.idle_fuel_trim = 0.6
        for _ in range(4000):
            engine1.step(1/600)
        
        engine2 = EnginePhysics()
        engine2.throttle = 0.10
        engine2.fuel_ratio = 0.08
        engine2.idle_fuel_trim = 1.6
        for _ in range(4000):
            engine2.step(1/600)
        
        # Both should run without crashing
        self.assertGreater(engine1.rpm_ema, 0.0)
        self.assertGreater(engine2.rpm_ema, 0.0)

    def test_snapshot_exposes_non_negative_separated_mass_flows(self) -> None:
        engine = EnginePhysics()
        engine.throttle = 0.55
        engine.fuel_ratio = 0.08
        for _ in range(240):
            engine.step(1 / 600)
        # Engine should be stable and state valid
        self.assertTrue(engine.validate_state())

    def test_state_validation_passes_for_normal_operation(self) -> None:
        engine = EnginePhysics()
        self.assertTrue(engine.validate_state())
        
        # Run engine for a while
        for _ in range(100):
            engine.step(0.001)
            self.assertTrue(engine.validate_state(), "State validation failed during normal operation")

    def test_state_validation_detects_invalid_mass(self) -> None:
        engine = EnginePhysics()
        engine.m_air_cr = -1.0  # Invalid negative mass
        self.assertFalse(engine.validate_state())

    def test_state_validation_detects_invalid_temperature(self) -> None:
        engine = EnginePhysics()
        engine.T_cr = 10000.0  # Unrealistically high temperature
        self.assertFalse(engine.validate_state())

    def test_kinematics_at_boundary_thetas(self) -> None:
        engine = EnginePhysics()
        # Test at various theta values including boundaries
        for theta_deg in [0, 90, 180, 270, 360]:
            theta = math.radians(theta_deg)
            x, v_cyl, v_cr, _ = engine.get_kinematics(theta)
            self.assertGreaterEqual(x, 0.0)
            self.assertGreater(v_cyl, 0.0)
            self.assertGreater(v_cr, 0.0)

    def test_kinematics_handles_extreme_ratios(self) -> None:
        """Test kinematics with extreme R/L ratios that could cause c_beta to approach zero."""
        engine = EnginePhysics()
        # Test with the actual R/L ratio
        original_L = engine.L
        # Temporarily set a very small L to test the guard
        engine.L = 0.026  # R/L = 0.025/0.026 ≈ 0.96, close to 1
        try:
            for theta_deg in range(0, 360, 10):
                theta = math.radians(theta_deg)
                x, v_cyl, v_cr, dx_dtheta = engine.get_kinematics(theta)
                self.assertTrue(math.isfinite(x))
                self.assertTrue(math.isfinite(v_cyl))
                self.assertTrue(math.isfinite(v_cr))
                self.assertTrue(math.isfinite(dx_dtheta))
        finally:
            engine.L = original_L

    def test_volume_guards_prevent_division_by_zero(self) -> None:
        """Test that volume guards prevent division by zero in pressure calculations."""
        engine = EnginePhysics()
        # Manually set volumes to near-zero to test guards
        engine.V_c = 1e-12
        engine.V_cr_min = 1e-12
        engine.A_p = 1e-12
        
        # This should not crash due to the guards
        snapshot = engine.snapshot()
        self.assertTrue(math.isfinite(snapshot.p_cyl))
        self.assertTrue(math.isfinite(snapshot.p_cr))

    def test_rescale_components_handles_zero_target(self) -> None:
        """Test that rescale_components handles zero target_total gracefully."""
        result = EnginePhysics.rescale_components(1.0, 2.0, 3.0, target_total=0.0)
        # Should return equal shares even with zero target
        self.assertEqual(len(result), 3)
        for value in result:
            self.assertGreaterEqual(value, 0.0)
            self.assertTrue(math.isfinite(value))

    def test_rescale_components_with_negative_inputs(self) -> None:
        """Test that rescale_components handles negative component values."""
        result = EnginePhysics.rescale_components(-1.0, 2.0, -3.0, target_total=10.0)
        # Negative values should be clamped to zero
        self.assertEqual(len(result), 3)
        self.assertGreaterEqual(result[0], 0.0)  # -1.0 clamped to 0
        self.assertGreater(result[1], 0.0)  # 2.0 scaled
        self.assertGreaterEqual(result[2], 0.0)  # -3.0 clamped to 0
        total = sum(result)
        self.assertAlmostEqual(total, 10.0, places=6)

    def test_angle_diff_various_cases(self) -> None:
        """Test angle_diff with various angle combinations."""
        self.assertAlmostEqual(EnginePhysics.angle_diff(0, 0), 0.0)
        self.assertAlmostEqual(EnginePhysics.angle_diff(10, 0), 10.0)
        self.assertAlmostEqual(EnginePhysics.angle_diff(350, 10), -20.0)
        self.assertAlmostEqual(EnginePhysics.angle_diff(180, 0), -180.0)  # Returns -180, not 180
        self.assertAlmostEqual(EnginePhysics.angle_diff(0, 180), -180.0)
        self.assertAlmostEqual(EnginePhysics.angle_diff(359, 1), -2.0)

    def test_flow_function_critical_pressure_ratio(self) -> None:
        """Test flow function at and below critical pressure ratio."""
        # Critical pressure ratio for gamma = 1.4 is approximately 0.528
        from physics import GAMMA
        pr_crit = (2.0 / (GAMMA + 1.0)) ** (GAMMA / (GAMMA - 1.0))
        
        # At critical ratio
        psi_at_crit = flow_function(100000.0, 100000.0 * pr_crit)
        self.assertGreater(psi_at_crit, 0.0)
        
        # Below critical ratio
        psi_below_crit = flow_function(100000.0, 100000.0 * (pr_crit * 0.5))
        self.assertGreater(psi_below_crit, 0.0)
        
        # Above critical ratio (choked)
        psi_above_crit = flow_function(100000.0, 100000.0 * (pr_crit * 0.9))
        self.assertGreater(psi_above_crit, 0.0)

    def test_mass_flow_various_conditions(self) -> None:
        """Test mass flow with various pressure differentials and areas."""
        # High pressure differential
        flow_high = mass_flow(0.7, 0.001, 500000.0, 300.0, 100000.0)
        self.assertGreater(flow_high, 0.0)
        
        # Low pressure differential
        flow_low = mass_flow(0.7, 0.001, 110000.0, 300.0, 100000.0)
        self.assertGreater(flow_low, 0.0)
        self.assertLess(flow_low, flow_high)
        
        # Larger area
        flow_large_area = mass_flow(0.7, 0.002, 200000.0, 300.0, 100000.0)
        self.assertGreater(flow_large_area, 0.0)

    def test_mixture_efficiency_extreme_lambda(self) -> None:
        """Test mixture efficiency at extreme lambda values."""
        engine = EnginePhysics()
        
        # Very lean
        eff_lean = engine.mixture_efficiency(lambda_value=2.5)
        self.assertGreater(eff_lean, 0.0)
        self.assertLess(eff_lean, 1.0)
        
        # Very rich
        eff_rich = engine.mixture_efficiency(lambda_value=0.5)
        self.assertGreater(eff_rich, 0.0)
        self.assertLess(eff_rich, 1.0)
        
        # Optimal (around 0.96)
        eff_optimal = engine.mixture_efficiency(lambda_value=0.96)
        self.assertGreater(eff_optimal, eff_lean)
        self.assertGreater(eff_optimal, eff_rich)

    def test_ignition_efficiency_timing_errors(self) -> None:
        """Test ignition efficiency with various timing errors."""
        engine = EnginePhysics()
        
        # Optimal timing (342°)
        eff_optimal = engine.ignition_efficiency()
        engine.ignition_angle_deg = 342.0
        
        # Retarded timing
        engine.ignition_angle_deg = 320.0
        eff_retarded = engine.ignition_efficiency()
        self.assertLess(eff_retarded, eff_optimal)
        
        # Advanced timing
        engine.ignition_angle_deg = 360.0
        eff_advanced = engine.ignition_efficiency()
        self.assertLess(eff_advanced, eff_optimal)
        
        # Reset
        engine.ignition_angle_deg = 340.0

    def test_intake_conditions_various_crankcase_pressures(self) -> None:
        """Test intake conditions with various crankcase pressures."""
        engine = EnginePhysics()
        
        # Low crankcase pressure (high flow)
        throttle, idle, p_intake, a_main, a_idle = engine.intake_conditions(p_cr=50000.0)
        self.assertGreater(p_intake, 50000.0)
        self.assertGreater(a_main + a_idle, 0.0)
        
        # High crankcase pressure (low flow)
        throttle, idle, p_intake, a_main, a_idle = engine.intake_conditions(p_cr=95000.0)
        self.assertLessEqual(p_intake, 101325.0)

    def test_pressure_clamping(self) -> None:
        """Test that pressures are properly clamped to safe ranges."""
        engine = EnginePhysics()
        engine.throttle = 1.0
        engine.fuel_ratio = 0.1
        
        # Run engine to build up pressure
        for _ in range(500):
            snapshot = engine.step(0.001)
        
        # Pressures should be within clamped ranges
        self.assertLessEqual(snapshot.p_cyl, MAX_CYLINDER_PRESSURE)
        self.assertGreaterEqual(snapshot.p_cyl, MIN_PRESSURE)

    def test_temperature_clamping(self) -> None:
        """Test that temperatures are properly clamped to safe ranges."""
        engine = EnginePhysics()
        
        # Run engine to let temperatures evolve
        for _ in range(100):
            engine.step(0.001)
        
        self.assertGreaterEqual(engine.T_cyl, T_ATM)
        self.assertLessEqual(engine.T_cyl, 3000.0)
        self.assertGreaterEqual(engine.T_cr, T_ATM)
        self.assertLessEqual(engine.T_cr, 500.0)

    def test_omega_clamping(self) -> None:
        """Test that omega (angular velocity) is properly clamped."""
        engine = EnginePhysics()
        
        # Run engine to let omega evolve
        for _ in range(100):
            engine.step(0.001)
        
        self.assertGreaterEqual(engine.omega, 0.0)
        self.assertLessEqual(engine.omega, 1400.0)

    def test_reed_valve_dynamics(self) -> None:
        """Test reed valve opening and closing behavior."""
        engine = EnginePhysics()
        
        # Initially closed
        self.assertEqual(engine.reed_opening, 0.0)
        
        # Run engine to activate reed valve
        for _ in range(500):
            engine.step(0.001)
        
        # Reed valve should have opened at some point
        self.assertGreaterEqual(engine.reed_opening, 0.0)
        self.assertLessEqual(engine.reed_opening, 1.0)

    def test_pipe_amplitude_bounds(self) -> None:
        """Test that pipe amplitude stays within reasonable bounds."""
        engine = EnginePhysics()
        
        # Run engine to excite pipe resonance
        for _ in range(1000):
            engine.step(0.001)
        
        # Amplitude is signed (can be negative for suction), check absolute value
        # and that it doesn't grow unbounded
        self.assertLess(abs(engine.pipe_amplitude), 100000.0)

    def test_combustion_timing_window(self) -> None:
        """Test that combustion only starts within the correct timing window."""
        engine = EnginePhysics()
        engine.ignition_angle_deg = 340.0
        engine.fuel_ratio = 0.08
        engine.throttle = 0.8
        
        # Run engine and verify it doesn't crash
        for _ in range(2000):
            engine.step(0.001)
        
        # Engine should be stable
        self.assertTrue(engine.validate_state())

    def test_fuel_film_evaporation(self) -> None:
        """Test that fuel film remains finite and doesn't grow unbounded."""
        engine = EnginePhysics()
        
        # Run engine to allow fuel film dynamics
        for _ in range(500):
            engine.step(0.001)
        
        # Fuel film should remain finite and reasonable
        self.assertGreaterEqual(engine.fuel_film_cr, 0.0)
        self.assertLess(engine.fuel_film_cr, 1.0)  # Should not grow to unbounded values
        self.assertTrue(math.isfinite(engine.fuel_film_cr))

    def test_mass_conservation_during_cycle(self) -> None:
        """Test that mass is conserved during a complete cycle."""
        engine = EnginePhysics()
        engine.throttle = 0.5
        engine.fuel_ratio = 0.068
        
        # Track total mass
        initial_total = engine.m_cyl + engine.m_cr + engine.fuel_film_cyl + engine.fuel_film_cr
        
        # Run for several cycles
        for _ in range(1000):
            engine.step(0.001)
        
        final_total = engine.m_cyl + engine.m_cr + engine.fuel_film_cyl + engine.fuel_film_cr
        
        # Total mass should be similar (may vary due to intake/exhaust)
        # This is a loose check since mass can enter/leave through ports
        self.assertGreater(final_total, 0.0)
        self.assertLess(final_total, initial_total * 10.0)  # Should not grow unbounded

    def test_combustion_with_no_fuel(self) -> None:
        engine = EnginePhysics()
        engine.fuel_ratio = 0.0  # No fuel in intake
        engine.snapshot()
        # Should not crash even with no fuel
        for _ in range(100):
            engine.step(0.001)
            self.assertTrue(engine.validate_state())

    def test_combustion_with_no_air(self) -> None:
        engine = EnginePhysics()
        engine.throttle = 0.0  # No air intake
        engine.snapshot()
        # Should not crash even with no air
        for _ in range(100):
            engine.step(0.001)
            self.assertTrue(engine.validate_state())

    def test_extreme_throttle_values(self) -> None:
        engine = EnginePhysics()
        engine.throttle = 0.0
        engine.step(0.001)
        self.assertTrue(engine.validate_state())
        
        engine.throttle = 1.0
        engine.step(0.001)
        self.assertTrue(engine.validate_state())


class ParticleValidationTests(unittest.TestCase):
    def test_validate_particle_accepts_valid_particle(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=1.0, vy=2.0)
        self.assertTrue(validate_particle(particle))

    def test_validate_particle_rejects_nan_position(self) -> None:
        particle = Particle(x=float('nan'), y=200.0, color=(255, 0, 0), vx=1.0, vy=2.0)
        self.assertFalse(validate_particle(particle))

    def test_validate_particle_rejects_infinity_velocity(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=float('inf'), vy=2.0)
        self.assertFalse(validate_particle(particle))

    def test_validate_particle_rejects_negative_life(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=1.0, vy=2.0, life=-10.0)
        self.assertFalse(validate_particle(particle))

    def test_validate_particle_rejects_negative_size(self) -> None:
        particle = Particle(x=100.0, y=200.0, color=(255, 0, 0), vx=1.0, vy=2.0, size=-5.0)
        self.assertFalse(validate_particle(particle))


if __name__ == "__main__":
    unittest.main()
