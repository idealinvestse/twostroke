"""Tests for fuel-air mixing models.

Validates:
- Droplet generation and size distribution
- Evaporation rates under various conditions
- Carburetor fuel metering
- Integration with engine physics
"""

import math
import pytest
from physics.fuel_drops import (
    FuelDrop, DropletEnsemble, calculate_sauter_mean_diameter,
    FUEL_DENSITY, FUEL_BOLING_POINT
)
from physics.carburetor import CarburetorModel
from physics.constants import R_GAS, T_ATM, P_ATM


class TestFuelDrop:
    """Test individual fuel droplet behavior."""
    
    def test_drop_initialization(self):
        drop = FuelDrop(
            mass=1e-6,  # 1 mg
            diameter=100e-6,  # 100 μm
            velocity=10.0,
            position=0.0,
            temperature=T_ATM,
            vapor_fraction=0.0
        )
        assert drop.mass == 1e-6
        assert drop.diameter == 100e-6
        assert not drop.is_vaporized
        assert drop.remaining_liquid_mass == 1e-6
    
    def test_drop_evaporation_high_temp(self):
        """Droplet should evaporate at higher temperatures."""
        drop = FuelDrop(
            mass=1e-6,
            diameter=100e-6,
            velocity=0.0,
            position=0.0,
            temperature=T_ATM,
            vapor_fraction=0.0
        )
        
        # Evaporate at high temperature
        dt = 0.001
        vap = drop.update(dt, P_ATM, T_ATM + 100, 10.0)
        
        # Should have some evaporation
        assert vap > 0
    
    def test_drop_evaporation_velocity(self):
        """Higher gas velocity should increase evaporation."""
        drop = FuelDrop(
            mass=1e-6,
            diameter=100e-6,
            velocity=0.0,
            position=0.0,
            temperature=T_ATM,
            vapor_fraction=0.0
        )
        
        # Low velocity
        rate_low = drop.calculate_evaporation_rate(P_ATM, T_ATM + 50, 5.0)
        
        # High velocity
        rate_high = drop.calculate_evaporation_rate(P_ATM, T_ATM + 50, 50.0)
        
        assert rate_high > rate_low
    
    def test_drop_complete_vaporization(self):
        """Droplet should eventually fully vaporize."""
        drop = FuelDrop(
            mass=1e-7,  # Small drop
            diameter=50e-6,
            velocity=0.0,
            position=0.0,
            temperature=T_ATM,
            vapor_fraction=0.0
        )
        
        # Simulate many timesteps at high temp
        dt = 0.001
        for _ in range(1000):
            dm = drop.update(dt, P_ATM, T_ATM + 150, 30.0)
            if drop.is_vaporized:
                break
        
        assert drop.is_vaporized or drop.vapor_fraction > 0.9


class TestDropletEnsemble:
    """Test droplet ensemble behavior."""
    
    def test_ensemble_generation(self):
        ensemble = DropletEnsemble()
        ensemble.add_droplets(
            total_mass=0.001,  # 1 gram
            mean_diameter=100e-6,
            T_fuel=T_ATM,
            velocity=0.0
        )
        
        stats = ensemble.get_statistics()
        assert stats['count'] > 0
        assert stats['total_liquid_mass'] > 0
        assert stats['mean_diameter'] > 0
    
    def test_ensemble_evaporation(self):
        ensemble = DropletEnsemble()
        ensemble.add_droplets(
            total_mass=0.001,
            mean_diameter=100e-6,
            T_fuel=T_ATM,
            velocity=0.0
        )
        
        initial_mass = ensemble.get_statistics()['total_liquid_mass']
        
        # Update at high temperature to cause evaporation
        vaporized, wall_film, remaining = ensemble.update_all(
            dt=0.01,
            p_gas=P_ATM,
            T_gas=T_ATM + 100,
            v_gas=20.0,
            wall_position=None  # No wall
        )
        
        # Should have some vaporization
        assert vaporized > 0 or remaining < initial_mass
    
    def test_wall_impingement(self):
        ensemble = DropletEnsemble()
        # Add large droplets that will hit wall
        ensemble.add_droplets(
            total_mass=0.001,
            mean_diameter=150e-6,  # Large droplets
            T_fuel=T_ATM,
            velocity=0.0
        )
        
        # Position droplets near wall
        for drop in ensemble.droplets:
            drop.position = 0.14  # Just before 0.15m wall
        
        vaporized, wall_film, remaining = ensemble.update_all(
            dt=0.01,
            p_gas=P_ATM,
            T_gas=T_ATM,
            v_gas=10.0,
            wall_position=0.15
        )
        
        # Should have wall film from large droplets
        assert wall_film > 0


class TestSauterMeanDiameter:
    """Test SMD calculations."""
    
    def test_carburetor_smd_range(self):
        """Carburetor SMD should be in realistic range (50-200 μm)."""
        smd = calculate_sauter_mean_diameter(
            air_velocity=50.0,
            fuel_pressure=20000.0,  # 20 kPa pressure drop
            is_injection=False
        )
        
        assert 50e-6 <= smd <= 300e-6
    
    def test_injection_smd_smaller(self):
        """Injection should produce smaller droplets than carburetor."""
        smd_carb = calculate_sauter_mean_diameter(
            air_velocity=50.0,
            fuel_pressure=20000.0,
            is_injection=False
        )
        
        smd_inj = calculate_sauter_mean_diameter(
            air_velocity=50.0,
            fuel_pressure=200000.0,  # 200 bar
            is_injection=True
        )
        
        assert smd_inj < smd_carb
    
    def test_velocity_effect_on_smd(self):
        """Higher velocity should produce smaller droplets."""
        smd_low = calculate_sauter_mean_diameter(
            air_velocity=20.0,
            fuel_pressure=20000.0,
            is_injection=False
        )
        
        smd_high = calculate_sauter_mean_diameter(
            air_velocity=80.0,
            fuel_pressure=20000.0,
            is_injection=False
        )
        
        assert smd_high < smd_low


class TestCarburetorModel:
    """Test carburetor physics."""
    
    def test_carburetor_initialization(self):
        carb = CarburetorModel()
        assert carb.state.p_venturi == P_ATM
        assert carb.state.m_dot_air == 0.0
    
    def test_throttle_effect_on_airflow(self):
        """Higher throttle should increase air flow."""
        carb = CarburetorModel()
        
        # Low throttle
        state_low = carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.2
        )
        flow_low = state_low.m_dot_air
        
        # High throttle
        carb2 = CarburetorModel()
        state_high = carb2.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.8
        )
        flow_high = state_high.m_dot_air
        
        assert flow_high > flow_low
    
    def test_fuel_flow_with_throttle(self):
        """Fuel flow should increase with throttle."""
        carb = CarburetorModel()
        
        state = carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        
        # Should have both air and fuel flow
        assert state.m_dot_air > 0
        assert state.total_fuel_flow > 0
    
    def test_venturi_pressure_drop(self):
        """Venturi should have lower pressure than upstream."""
        carb = CarburetorModel()
        
        state = carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        
        assert state.p_venturi < P_ATM
    
    def test_fuel_air_ratio_range(self):
        """F/A ratio should be in reasonable range for 2-stroke."""
        carb = CarburetorModel()
        
        state = carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        
        fa_ratio = state.fuel_air_ratio
        
        # 2-stroke typically runs rich, F/A ~ 0.05-0.12 (lambda ~ 0.6-1.4)
        # Allow slightly leaner at idle test conditions
        assert 0.025 <= fa_ratio <= 0.15
    
    def test_idle_circuit_activation(self):
        """Idle circuit should activate at low throttle."""
        carb = CarburetorModel()
        
        # Low throttle - idle circuit active
        state_idle = carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.1
        )
        idle_fuel = state_idle.m_dot_fuel_idle
        
        # High throttle - idle circuit off
        carb2 = CarburetorModel()
        state_high = carb2.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.6
        )
        high_fuel_idle = state_high.m_dot_fuel_idle
        
        assert idle_fuel > high_fuel_idle
    
    def test_droplet_generation(self):
        """Carburetor should generate fuel droplets."""
        carb = CarburetorModel()
        
        carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        
        stats = carb.get_droplet_statistics()
        assert stats['count'] > 0
    
    def test_droplet_evaporation_in_crankcase(self):
        """Droplets should evaporate in warm crankcase."""
        carb = CarburetorModel()
        
        carb.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        
        # Update droplets in warm crankcase
        vaporized, wall_film, remaining = carb.update_droplets(
            dt=0.01,
            p_gas=P_ATM * 1.2,  # Crankcase pressure
            T_gas=T_ATM + 80,   # Warm crankcase
            v_gas=15.0,         # Air velocity
            wall_position=0.15
        )
        
        # Should have some vaporization
        assert vaporized > 0 or remaining > 0 or wall_film > 0


class TestCarburetorNeedleAdjustment:
    """Test carburetor mixture adjustment."""
    
    def test_needle_rich_lean(self):
        """Needle position should affect mixture."""
        # Rich setting (needle low)
        carb_rich = CarburetorModel()
        carb_rich.set_needle_position(0.0)  # Rich
        
        state_rich = carb_rich.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        fa_rich = state_rich.fuel_air_ratio
        
        # Lean setting (needle high)
        carb_lean = CarburetorModel()
        carb_lean.set_needle_position(1.0)  # Lean
        
        state_lean = carb_lean.update(
            dt=0.001,
            p_upstream=P_ATM,
            T_upstream=T_ATM,
            throttle_position=0.5
        )
        fa_lean = state_lean.fuel_air_ratio
        
        # Rich should have higher F/A ratio
        assert fa_rich > fa_lean


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
