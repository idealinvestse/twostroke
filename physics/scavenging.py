"""
Advanced multi-zone scavenging model for 2-stroke engines.

Implements RPM- and geometry-dependent scavenging with multiple zones:
- Fresh charge zone
- Residual burned gas zone
- Short-circuit loss zone
- Mixing zone

Based on empirical correlations from 2-stroke engine research.
"""

from dataclasses import dataclass, field
from typing import Tuple
import math

from physics.constants import (
    R_GAS,
    P_ATM,
    T_ATM,
    DISPLACEMENT_M3,
    BORE_M,
    HALF_STROKE_M,
)
from physics.utils import clamp


@dataclass
class ScavengingZones:
    """Multi-zone scavenging state with zone tracking."""
    # Fresh charge zones
    fresh_direct: float = 0.0  # Fresh charge directly entering cylinder (kg)
    fresh_mixed: float = 0.0   # Fresh charge mixed with residuals (kg)
    
    # Residual zones
    residual_displaced: float = 0.0  # Residuals pushed out (kg)
    residual_trapped: float = 0.0    # Residuals remaining in cylinder (kg)
    
    # Short-circuit zone
    short_circuit: float = 0.0  # Fresh charge lost directly to exhaust (kg)
    
    # Mixing zone
    mixing_fresh: float = 0.0   # Fresh in mixing zone (kg)
    mixing_residual: float = 0.0  # Residual in mixing zone (kg)
    
    @property
    def total_fresh(self) -> float:
        """Total fresh charge retained."""
        return self.fresh_direct + self.fresh_mixed + self.mixing_fresh
    
    @property
    def total_residual(self) -> float:
        """Total residual gas retained."""
        return self.residual_trapped + self.mixing_residual
    
    @property
    def total_mass(self) -> float:
        """Total mass in cylinder."""
        return self.total_fresh + self.total_residual
    
    @property
    def charge_purity(self) -> float:
        """Fraction of fresh charge in cylinder."""
        return self.total_fresh / max(self.total_mass, 1e-9)


@dataclass
class ScavengingMetrics:
    """Efficiency metrics for scavenging."""
    scavenging_efficiency: float  # Fraction of residuals displaced
    trapping_efficiency: float   # Fraction of fresh charge retained
    delivery_ratio: float       # Delivered / cylinder displacement
    volumetric_efficiency: float # Actual fill / theoretical fill
    lambda_scav: float          # Delivery ratio (same as delivery_ratio)
    
    # Zone fractions
    fresh_fraction: float  # Fraction of cylinder that is fresh charge
    residual_fraction: float  # Fraction that is residual
    short_circuit_fraction: float  # Fraction delivered that short-circuits


class AdvancedScavengingModel:
    """Advanced multi-zone scavenging model with RPM and geometry dependence.
    
    Implements empirical correlations for:
    - RPM-dependent scavenging efficiency
    - Port timing effects (exhaust/transfer overlap)
    - Port area effects
    - Multi-zone mixing and displacement
    
    Based on:
    - Blair's 2-stroke engine scavenging correlations
    - Heywood's empirical scavenging models
    - SAE papers on 2-stroke scavenging optimization
    """
    
    def __init__(
        self,
        bore: float = BORE_M,
        stroke: float = 2 * HALF_STROKE_M,
        displacement: float = DISPLACEMENT_M3,
    ) -> None:
        """Initialize advanced scavenging model.
        
        Args:
            bore: Cylinder bore diameter (m)
            stroke: Piston stroke (m)
            displacement: Cylinder displacement volume (m³)
        """
        self.bore = bore
        self.stroke = stroke
        self.displacement = displacement
        
        # Base scavenging parameters (calibrated for typical 50cc engine)
        self.base_scavenging_efficiency = 0.75  # At optimal RPM
        self.base_trapping_efficiency = 0.80   # At optimal RPM
        self.optimal_rpm = 8000.0  # RPM for peak scavenging
        
        # RPM sensitivity parameters
        self.rpm_sensitivity = 0.15  # How much scavenging varies with RPM
        self.rpm_width = 3000.0  # Width of RPM curve (sigma)
        
        # Port geometry sensitivity
        self.port_overlap_sensitivity = 0.20  # Effect of exhaust/transfer overlap
        self.port_area_sensitivity = 0.10     # Effect of port area ratio
        
        # Zone parameters
        self.displacement_fraction = 0.60  # Fraction of scavenging that is displacement
        self.mixing_fraction = 0.30        # Fraction that is mixing
        self.short_circuit_base = 0.10     # Base short-circuit fraction
    
    def calculate_rpm_factor(self, rpm: float) -> float:
        """Calculate RPM-dependent scavenging factor.
        
        Uses Gaussian-like curve centered at optimal RPM.
        
        Args:
            rpm: Engine RPM
            
        Returns:
            Factor (0-1) representing RPM effect on scavenging
        """
        # Gaussian curve centered at optimal RPM
        delta_rpm = (rpm - self.optimal_rpm) / self.rpm_width
        rpm_factor = math.exp(-delta_rpm ** 2)
        
        # Add linear drop-off at very high RPM
        if rpm > self.optimal_rpm + self.rpm_width:
            excess = (rpm - self.optimal_rpm - self.rpm_width) / 5000.0
            rpm_factor *= max(0.5, 1.0 - 0.3 * excess)
        
        return clamp(rpm_factor, 0.3, 1.0)
    
    def calculate_port_geometry_factor(
        self,
        exhaust_port_height: float,
        transfer_port_height: float,
        port_overlap_deg: float,
    ) -> Tuple[float, float]:
        """Calculate port geometry effects on scavenging.
        
        Args:
            exhaust_port_height: Exhaust port opening height (m)
            transfer_port_height: Transfer port opening height (m)
            port_overlap_deg: Overlap between exhaust and transfer (degrees)
            
        Returns:
            Tuple of (displacement_factor, short_circuit_factor)
        """
        # Port timing ratio (transfer opens after exhaust closes)
        # Positive overlap means both open simultaneously
        overlap_factor = clamp(port_overlap_deg / 30.0, 0.0, 1.0)
        
        # Port height ratio (transfer / exhaust)
        height_ratio = clamp(transfer_port_height / max(exhaust_port_height, 1e-6), 0.5, 1.5)
        
        # Displacement improves with good port timing
        displacement_factor = 1.0 + self.port_overlap_sensitivity * overlap_factor * height_ratio
        
        # Short-circuit increases with overlap (fresh charge can escape directly)
        short_circuit_factor = self.short_circuit_base + 0.15 * overlap_factor
        
        return clamp(displacement_factor, 0.8, 1.2), clamp(short_circuit_factor, 0.05, 0.4)
    
    def calculate_multi_zone_scavenging(
        self,
        m_fresh_delivered: float,
        m_residual_initial: float,
        m_fresh_initial: float,
        rpm: float,
        exhaust_port_height: float,
        transfer_port_height: float,
        port_overlap_deg: float,
        cylinder_volume: float,
    ) -> Tuple[ScavengingZones, ScavengingMetrics]:
        """Calculate multi-zone scavenging with RPM and geometry dependence.
        
        Args:
            m_fresh_delivered: Fresh charge delivered via transfer (kg)
            m_residual_initial: Initial residual mass in cylinder (kg)
            m_fresh_initial: Initial fresh charge in cylinder (kg)
            rpm: Engine RPM
            exhaust_port_height: Exhaust port opening height (m)
            transfer_port_height: Transfer port opening height (m)
            port_overlap_deg: Port overlap in degrees
            cylinder_volume: Current cylinder volume (m³)
            
        Returns:
            Tuple of (ScavengingZones, ScavengingMetrics)
        """
        m_total_initial = m_fresh_initial + m_residual_initial
        
        # Calculate RPM factor
        rpm_factor = self.calculate_rpm_factor(rpm)
        
        # Calculate port geometry factors
        disp_factor, short_circuit_factor = self.calculate_port_geometry_factor(
            exhaust_port_height, transfer_port_height, port_overlap_deg
        )
        
        # Delivery ratio
        m_displacement_fill = cylinder_volume * P_ATM / (R_GAS * T_ATM)
        delivery_ratio = clamp(m_fresh_delivered / max(m_displacement_fill, 1e-9), 0.0, 3.0)
        
        # Initialize zones
        zones = ScavengingZones()
        
        # Short-circuit zone (loss)
        zones.short_circuit = m_fresh_delivered * short_circuit_factor * (1.0 - 0.3 * rpm_factor)
        m_fresh_effective = m_fresh_delivered - zones.short_circuit
        
        # Displacement zone (fresh pushes out residual)
        displacement_efficiency = self.displacement_fraction * self.base_scavenging_efficiency * rpm_factor * disp_factor
        displacement_efficiency = clamp(displacement_efficiency, 0.0, 0.95)
        
        m_residual_displaced = m_residual_initial * displacement_efficiency * min(1.0, delivery_ratio)
        zones.residual_displaced = m_residual_displaced
        zones.residual_trapped = max(0.0, m_residual_initial - m_residual_displaced)
        
        # Fresh charge that displaces residuals
        zones.fresh_direct = min(m_fresh_effective, m_residual_displaced)
        m_fresh_remaining = max(0.0, m_fresh_effective - zones.fresh_direct)
        
        # Mixing zone (remaining fresh mixes with trapped residuals)
        if m_fresh_remaining > 0 and zones.residual_trapped > 0:
            mixing_efficiency = self.mixing_fraction * rpm_factor
            mixing_ratio = (m_fresh_remaining / max(m_total_initial, 1e-9)) * mixing_efficiency
            
            # Exponential mixing model
            zones.mixing_residual = zones.residual_trapped * math.exp(-mixing_ratio)
            zones.mixing_fresh = m_fresh_remaining * (1.0 - math.exp(-mixing_ratio))
            
            # Any remaining fresh goes to direct zone
            zones.fresh_direct += m_fresh_remaining - zones.mixing_fresh
        else:
            zones.mixing_residual = zones.residual_trapped
            zones.mixing_fresh = 0.0
            zones.fresh_direct += m_fresh_remaining
        
        # Add initial fresh charge
        zones.fresh_direct += m_fresh_initial
        
        # Calculate metrics
        scav_eff = 1.0 - (zones.total_residual / max(m_residual_initial, 1e-9))
        trap_eff = (zones.total_fresh - m_fresh_initial) / max(m_fresh_delivered, 1e-9)
        vol_eff = zones.total_fresh / max(m_displacement_fill, 1e-9)
        
        metrics = ScavengingMetrics(
            scavenging_efficiency=clamp(scav_eff, 0.0, 1.0),
            trapping_efficiency=clamp(trap_eff, 0.0, 1.0),
            delivery_ratio=delivery_ratio,
            volumetric_efficiency=clamp(vol_eff, 0.0, 1.5),
            lambda_scav=delivery_ratio,
            fresh_fraction=zones.charge_purity,
            residual_fraction=1.0 - zones.charge_purity,
            short_circuit_fraction=zones.short_circuit / max(m_fresh_delivered, 1e-9),
        )
        
        return zones, metrics
    
    def get_optimal_port_timing(
        self,
        rpm: float,
    ) -> Tuple[float, float]:
        """Calculate optimal port timing for given RPM.
        
        Args:
            rpm: Target RPM
            
        Returns:
            Tuple of (optimal_exhaust_height, optimal_transfer_height) in meters
        """
        rpm_factor = self.calculate_rpm_factor(rpm)
        
        # At higher RPM, want later exhaust opening (shorter blowdown)
        # and earlier transfer opening (more scavenging time)
        
        base_exhaust_height = 0.022  # 22mm typical
        base_transfer_height = 0.025  # 25mm typical
        
        # Adjust for RPM
        if rpm > self.optimal_rpm:
            factor = 1.0 - 0.1 * (rpm - self.optimal_rpm) / 5000.0
            optimal_exhaust = base_exhaust_height * clamp(factor, 0.8, 1.0)
            optimal_transfer = base_transfer_height * clamp(factor, 0.9, 1.1)
        else:
            factor = 1.0 + 0.1 * (self.optimal_rpm - rpm) / 3000.0
            optimal_exhaust = base_exhaust_height * clamp(factor, 0.9, 1.1)
            optimal_transfer = base_transfer_height * clamp(factor, 0.8, 1.0)
        
        return optimal_exhaust, optimal_transfer
