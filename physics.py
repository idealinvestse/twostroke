from dataclasses import dataclass
import math

R_GAS = 287.05
C_V = 718.0
C_P = 1005.0
GAMMA = C_P / C_V
P_ATM = 101325.0
T_ATM = 293.15
MIN_PRESSURE = 20000.0
MIN_CRANKCASE_PRESSURE = 35000.0
MAX_CYLINDER_PRESSURE = 8_000_000.0
MAX_CRANKCASE_PRESSURE = 250_000.0
MAX_OMEGA = 950.0
FUEL_LHV = 44_000_000.0
STOICH_AFR = 14.7


def flow_function(p_up: float, p_down: float) -> float:
    if p_up <= 0:
        return 0.0
    pr = p_down / p_up
    if pr >= 1.0:
        return 0.0
    pr = max(pr, 0.001)
    pr_crit = (2.0 / (GAMMA + 1.0)) ** (GAMMA / (GAMMA - 1.0))
    if pr < pr_crit:
        pr = pr_crit
    term = (pr ** (2.0 / GAMMA)) - (pr ** ((GAMMA + 1.0) / GAMMA))
    return math.sqrt(abs(2.0 * GAMMA / (GAMMA - 1.0) * max(0.0, term)) + 1e-9)


def mass_flow(c_d: float, area: float, p_up: float, t_up: float, p_down: float) -> float:
    if p_up <= p_down or area <= 0:
        return 0.0
    psi = flow_function(p_up, p_down)
    return c_d * area * p_up / math.sqrt(R_GAS * max(1.0, t_up)) * psi


@dataclass
class EngineSnapshot:
    x: float
    p_cyl: float
    p_cr: float
    p_exh_pipe: float
    a_exh: float
    a_tr: float
    a_in: float
    rpm: float
    torque: float
    power_kw: float
    dm_exh: float
    dm_tr: float
    dm_in: float
    dm_air_in: float
    dm_fuel_in: float
    dm_air_tr: float
    dm_fuel_tr: float
    dm_burned_tr: float
    dm_air_exh: float
    dm_fuel_exh: float
    dm_burned_exh: float
    volumetric_efficiency: float
    trapping_efficiency: float


class EnginePhysics:
    def __init__(self) -> None:
        self.B = 0.054  # 54mm bore
        self.R = 0.025  # 50mm stroke (R is half stroke)
        self.L = 0.095  # 95mm connecting rod
        self.A_p = math.pi * (self.B / 2) ** 2
        self.V_d = self.A_p * 2 * self.R
        self.V_c = self.V_d / 7.5  # 8.5:1 compression ratio (V_d + V_c) / V_c = 8.5
        self.V_cr_min = self.V_d * 1.8  # Realistic crankcase volume for 2-stroke scavenging
        self.I_engine = 0.008  # Lower inertia for snappier response
        self.friction = 0.65    # Realistic friction for this engine size
        self.A_in_max = 0.0012
        self.theta = math.radians(18.0)
        self.omega = 90.0
        self.sim_time = 0.0
        self.starter_duration = 0.8
        self.starter_torque = 4.0
        self.idle_omega_target = 115.0
        self.throttle = 1.0
        self.fuel_ratio = 0.068
        self.idle_fuel_trim = 1.0

        # === TRIMMING-PARAMETRAR ===
        # Dessa kan justeras för att simulera olika trimningsalternativ

        # Motor-geometri
        self.stroke_multiplier = 1.0  # 0.8-1.2, ändrar slagläge
        self.bore_multiplier = 1.0    # 0.9-1.15, ändrar borr-diameter
        self.compression_ratio = 7.5  # 6.0-10.0, kompressionsförhållande
        self.rod_length = 0.095       # 0.08-0.12, plejlstångslängd

        # Scavenging & portar
        self.transfer_port_height = 0.034  # 0.025-0.045, överföringsport-höjd
        self.exhaust_port_height = 0.024   # 0.018-0.035, avgasport-höjd
        self.exhaust_port_width = 0.038    # 0.030-0.050, avgasport-bredd
        self.transfer_port_width = 0.032   # 0.025-0.045, överföringsport-bredd
        self.port_overlap = 0.0           # -5 till +10 grader, port-överlapp

        # Avgassystem (expansion chamber)
        self.pipe_resonance_freq = 140.0   # 80-200 Hz, resonansfrekvens
        self.pipe_length = 1.0             # 0.5-1.5, relativ pip-längd
        self.pipe_q_factor = 2.5           # 1.5-4.0, Q-faktor (dämpning)
        self.pipe_amplitude = 0.0
        self.pipe_phase = 0.0

        # Tändning & förbränning
        self.burn_duration_factor = 1.0    # 0.7-1.4, förbränningstid
        self.combustion_efficiency = 1.0   # 0.7-1.0, förbränningsverkningsgrad
        self.spark_duration = 0.002        # 0.001-0.005, gnistlängd (sek)
        self.ignition_advance_range = 18.0 # 10-30 grader, optimal avvikelse

        # Bränsle & insug
        self.fuel_evap_rate_cr = 1.0       # 0.5-2.0, vevhus-bränsle-förångning
        self.fuel_evap_rate_cyl = 1.0      # 0.5-2.0, cylinder-bränsle-förångning
        self.reed_stiffness = 1200.0       # 800-2000, vevhusventil-styvhet
        self.idle_circuit_strength = 1.0   # 0.5-1.5, tomgångskrets-styrka

        # Mekaniskt
        self.inertia_multiplier = 1.0      # 0.6-1.5, tröghet (svänghjul)
        self.friction_factor = 1.0         # 0.7-1.3, friktionsfaktor
        self.mechanical_efficiency = 0.85  # 0.75-0.92, mekanisk verkningsgrad
        self.spark_active = False
        self.ignition_enabled = True
        self.fuel_cutoff = False
        self.reed_opening = 0.0
        self.reed_velocity = 0.0
        self.m_cyl = self.V_c * P_ATM / (R_GAS * T_ATM)
        self.T_cyl = T_ATM
        self.m_cr = self.V_cr_min * P_ATM / (R_GAS * T_ATM)
        self.T_cr = T_ATM
        crankcase_fuel_air_ratio = self.target_fuel_air_ratio()
        self.m_fuel_cr = self.m_cr * crankcase_fuel_air_ratio / (1.0 + crankcase_fuel_air_ratio)
        self.fuel_film_cr = self.m_fuel_cr * 0.35
        self.fuel_film_cyl = 0.0
        self.m_fuel_cr -= self.fuel_film_cr
        self.m_air_cr = self.m_cr - self.m_fuel_cr
        self.m_residual_cr = 0.0
        self.m_burned_cyl = self.m_cyl * 0.12
        self.m_fuel_cyl = 0.0
        self.m_air_cyl = self.m_cyl - self.m_burned_cyl
        self.x_b_cyl = self.m_burned_cyl / max(self.m_cyl, 1e-9)
        self.ignition_angle_deg = 340
        self.combustion_active = False
        self.theta_ign = 0.0
        self.burn_fraction = 0.0
        self.burn_duration = math.radians(40.0)
        self.combustible_fuel_mass = 0.0
        self.combustion_efficiency = 1.0
        self.lambda_value = 1.0
        self.cycle_air_in = 0.0
        self.cycle_air_tr = 0.0
        self.cycle_air_exh = 0.0
        self.volumetric_efficiency = 0.0
        self.trapping_efficiency = 0.0
        self.last_theta_cross = 0.0

        # Output smoothing
        self.rpm_ema = 0.0
        self.torque_ema = 0.0
        self.power_ema = 0.0
        self.cycle_work = 0.0
        self.last_cycle_torque = 0.0
        
        # Simple tuned pipe model - uses values from tuning parameters above

    @staticmethod
    def angle_diff(a: float, b: float) -> float:
        return (a - b + 180.0) % 360.0 - 180.0

    def validate_state(self) -> bool:
        """Check for NaN or infinity values in critical state variables.
        Returns True if state is valid, False otherwise."""
        import math
        
        # Check critical scalar values
        critical_values = [
            self.theta, self.omega, self.sim_time,
            self.T_cyl, self.T_cr,
            self.m_cyl, self.m_cr,
            self.m_air_cyl, self.m_fuel_cyl, self.m_burned_cyl,
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr,
            self.lambda_value, self.burn_fraction,
        ]
        
        for value in critical_values:
            if not math.isfinite(value):
                return False
        
        # Check that masses are non-negative
        if any(m < -1e-9 for m in [
            self.m_cyl, self.m_cr,
            self.m_air_cyl, self.m_fuel_cyl, self.m_burned_cyl,
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr,
            self.fuel_film_cyl, self.fuel_film_cr,
        ]):
            return False
        
        # Check temperatures are within reasonable bounds
        if not (T_ATM <= self.T_cyl <= 5000.0):
            return False
        if not (T_ATM <= self.T_cr <= 1000.0):
            return False
        
        # Check omega is non-negative
        if self.omega < 0:
            return False
        
        return True

    def target_fuel_air_ratio(self) -> float:
        return self.fuel_ratio / max(1e-6, 1.0 - self.fuel_ratio)

    def throttle_flow_factor(self) -> float:
        return 0.04 + 0.96 * (self.throttle ** 1.35)

    def get_idle_circuit_strength(self) -> float:
        return max(0.0, min(1.0, (0.32 - self.throttle) / 0.32))

    def intake_conditions(self, p_cr: float) -> tuple[float, float, float, float, float]:
        throttle_factor = self.throttle_flow_factor()
        idle_circuit = self.get_idle_circuit_strength()
        p_intake = min(P_ATM, P_ATM * (0.35 + 0.65 * throttle_factor) + P_ATM * 0.04 * idle_circuit * self.idle_fuel_trim)
        if p_intake <= p_cr:
            return throttle_factor, idle_circuit, p_intake, 0.0, 0.0
        a_main = self.A_in_max * throttle_factor
        a_idle = self.A_in_max * 0.09 * idle_circuit * (0.35 + 0.65 * self.idle_fuel_trim)
        return throttle_factor, idle_circuit, p_intake, a_main, a_idle

    def mixture_efficiency(self, lambda_value: float | None = None) -> float:
        current_lambda = self.lambda_value if lambda_value is None else lambda_value
        efficiency = math.exp(-((current_lambda - 0.92) / 0.35) ** 2)
        return max(0.18, min(1.02, efficiency))

    def ignition_efficiency(self) -> float:
        optimal_ignition = 342.0
        ignition_error = self.angle_diff(self.ignition_angle_deg, optimal_ignition)
        efficiency = math.exp(-((ignition_error / 18.0) ** 2))
        return max(0.35, min(1.0, efficiency))

    @staticmethod
    def rescale_components(*components: float, target_total: float) -> tuple[float, ...]:
        positive_components = [max(0.0, component) for component in components]
        total = sum(positive_components)
        # Guard against zero target_total
        target_total = max(target_total, 1e-12)
        if total <= 1e-12:
            share = target_total / max(1, len(positive_components))
            return tuple(share for _ in positive_components)
        scale = target_total / total
        return tuple(component * scale for component in positive_components)

    def get_kinematics(self, theta: float) -> tuple[float, float, float, float]:
        s_theta = math.sin(theta)
        c_theta = math.cos(theta)
        
        # Använd trimnings-parametrar för vevmekanism
        R_eff = self.R * self.stroke_multiplier
        L_eff = self.rod_length
        
        # Clamp argument to asin to prevent domain errors from floating-point drift
        beta_arg = max(-1.0, min(1.0, R_eff / L_eff * s_theta))
        beta = math.asin(beta_arg)
        c_beta = math.cos(beta)
        # Guard against division by zero when c_beta approaches zero
        c_beta = max(c_beta, 1e-6)
        x = R_eff + L_eff - (R_eff * c_theta + L_eff * c_beta)
        dx_dtheta = R_eff * s_theta * (1 + R_eff * c_theta / (L_eff * c_beta))
        v_cyl = self.V_c + self.A_p * x
        v_cr = self.V_cr_min + self.A_p * (2 * R_eff - x)
        return x, v_cyl, v_cr, dx_dtheta

    def snapshot(self) -> EngineSnapshot:
        x, v_cyl, v_cr, _ = self.get_kinematics(self.theta)
        self.m_cyl = self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl
        self.m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        # Guard against zero volumes in pressure calculations
        v_cyl = max(v_cyl, 1e-9)
        v_cr = max(v_cr, 1e-9)
        p_cyl = min(MAX_CYLINDER_PRESSURE, max(MIN_PRESSURE, self.m_cyl * R_GAS * self.T_cyl / v_cyl))
        p_cr = min(MAX_CRANKCASE_PRESSURE, max(MIN_CRANKCASE_PRESSURE, self.m_cr * R_GAS * self.T_cr / v_cr))
        a_exh = max(0.0, x - self.exhaust_port_height) * self.exhaust_port_width
        a_tr = max(0.0, x - self.transfer_port_height) * self.transfer_port_width
        _, _, _, a_main, a_idle = self.intake_conditions(p_cr)
        a_in = a_main + a_idle
        return EngineSnapshot(
            x=x,
            p_cyl=p_cyl,
            p_cr=p_cr,
            p_exh_pipe=self.p_pipe,
            a_exh=a_exh,
            a_tr=a_tr,
            a_in=a_in,
            rpm=self.rpm_ema,
            torque=self.torque_ema,
            power_kw=self.power_ema,
            dm_exh=0.0,
            dm_tr=0.0,
            dm_in=0.0,
            dm_air_in=0.0,
            dm_fuel_in=0.0,
            dm_air_tr=0.0,
            dm_fuel_tr=0.0,
            dm_burned_tr=0.0,
            dm_air_exh=0.0,
            dm_fuel_exh=0.0,
            dm_burned_exh=0.0,
            volumetric_efficiency=self.volumetric_efficiency,
            trapping_efficiency=self.trapping_efficiency,
        )

    def step(self, dt: float, starter_active: bool = False) -> EngineSnapshot:
        if dt > 0.01:
            dt = 0.01
        self.sim_time += dt
        x, v_cyl, v_cr, dx_dtheta = self.get_kinematics(self.theta)
        self.m_cyl = self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl
        self.m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        # Guard against zero volumes in pressure calculations
        v_cyl = max(v_cyl, 1e-9)
        v_cr = max(v_cr, 1e-9)
        p_cyl = min(MAX_CYLINDER_PRESSURE, max(MIN_PRESSURE, self.m_cyl * R_GAS * self.T_cyl / v_cyl))
        p_cr = min(MAX_CRANKCASE_PRESSURE, max(MIN_CRANKCASE_PRESSURE, self.m_cr * R_GAS * self.T_cr / v_cr))
        a_exh = max(0.0, x - self.exhaust_port_height) * self.exhaust_port_width
        a_tr = max(0.0, x - self.transfer_port_height) * self.transfer_port_width
        throttle_factor, idle_circuit, p_intake, a_main, a_idle = self.intake_conditions(p_cr)
        pressure_diff = p_intake - p_cr
        reed_force = pressure_diff * 0.02 - self.reed_opening * self.reed_stiffness - self.reed_velocity * 40.0
        self.reed_velocity += reed_force * dt
        self.reed_opening += self.reed_velocity * dt
        if self.reed_opening < 0.0:
            self.reed_opening = 0.0
            self.reed_velocity = 0.0
        elif self.reed_opening > 1.0:
            self.reed_opening = 1.0
            self.reed_velocity = 0.0
        a_in = (a_main + a_idle) * self.reed_opening
        
        # Expansion chamber logic
        # Instead of simple sine wave, we simulate a pressure pulse traveling and returning
        self.pipe_phase += self.omega * dt * 2.0  # Double frequency for simpler resonant effects
        # Normalize phase to prevent unbounded growth
        self.pipe_phase %= 2.0 * math.pi
        pipe_suction_effect = math.sin(self.pipe_phase) * self.pipe_amplitude
        # Decay amplitude towards neutral when exhaust is closed
        if a_exh < 1e-6:
            self.pipe_amplitude *= math.exp(-15.0 * dt)
        
        # Limit max amplitude of pipe pressure wave to realistic bounds (~0.4 bar below, ~0.6 bar above atm)
        pipe_suction_effect = max(-60000.0, min(40000.0, pipe_suction_effect))
        self.p_pipe = P_ATM - pipe_suction_effect

        if p_cyl > self.p_pipe:
            dm_exh = mass_flow(0.7, a_exh, p_cyl, self.T_cyl, self.p_pipe)
            # Add energy to the pipe resonance
            current_hz = self.omega / (2 * math.pi)
            hz_diff = abs(current_hz - self.pipe_resonance_freq)
            q_factor_denom = max(self.pipe_q_factor, 1e-6)
            resonance_freq_denom = max(self.pipe_resonance_freq, 1e-6)
            resonance_efficiency = math.exp(-((hz_diff / (resonance_freq_denom / q_factor_denom)) ** 2))
            self.pipe_amplitude += dm_exh * dt * 60000.0 * resonance_efficiency
        else:
            # Backflow from pipe (stuffing) - add burned residual gas proportionally
            dm_exh = -mass_flow(0.7, a_exh, self.p_pipe, self.T_cyl * 0.9, p_cyl)
            if dm_exh < 0 and not self.fuel_cutoff:
                # Backflow: add gas from pipe (treated as burned residual + air mix)
                backflow_mass = -dm_exh * dt
                # Assume backflow is primarily burned gas with some fresh charge
                self.m_burned_cyl += backflow_mass * 0.85
                self.m_air_cyl += backflow_mass * 0.15
            
        if p_cr > p_cyl:
            dm_tr = mass_flow(0.7, a_tr, p_cr, self.T_cr, p_cyl)
        else:
            dm_tr = 0.0
        if p_intake > p_cr and not self.fuel_cutoff:
            dm_air_main = mass_flow(0.72, a_main, p_intake, T_ATM, p_cr)
            dm_air_idle = mass_flow(0.66, a_idle, P_ATM, T_ATM, p_cr)
        else:
            dm_air_main = 0.0
            dm_air_idle = 0.0
        dm_air_in = dm_air_main + dm_air_idle
        intake_signal = max(0.0, min(1.4, (p_intake - p_cr) / P_ATM))
        target_fuel_air_ratio = self.target_fuel_air_ratio()
        main_fuel_signal = 0.85 + 0.5 * math.sqrt(intake_signal + 1e-9)
        idle_fuel_signal = (0.82 + 0.45 * self.idle_fuel_trim) * (0.35 + 0.65 * idle_circuit)
        raw_fuel_main = dm_air_main * target_fuel_air_ratio * main_fuel_signal
        raw_fuel_idle = dm_air_idle * target_fuel_air_ratio * idle_fuel_signal
        crankcase_wet_fraction = max(0.15, 0.50 - 0.30 * throttle_factor)
        crankcase_evap_rate = 1.5 + 4.0 * throttle_factor + 0.02 * max(0.0, self.T_cr - T_ATM)
        crankcase_film_added = (raw_fuel_main + raw_fuel_idle) * crankcase_wet_fraction * dt
        self.fuel_film_cr += crankcase_film_added
        crankcase_evaporated = min(self.fuel_film_cr, self.fuel_film_cr * crankcase_evap_rate * dt)
        self.fuel_film_cr -= crankcase_evaporated
        dm_fuel_in = (raw_fuel_main + raw_fuel_idle) * (1.0 - crankcase_wet_fraction) + crankcase_evaporated / max(dt, 1e-6)
        dm_in = dm_air_in + dm_fuel_in
        self.m_air_cr += dm_air_in * dt
        self.m_fuel_cr += dm_fuel_in * dt
        dm_air_tr = 0.0
        dm_fuel_tr = 0.0
        dm_burned_tr = 0.0
        if dm_tr > 0.0 and not self.fuel_cutoff:
            transfer_mass = min(dm_tr * dt, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
            crankcase_total = max(1e-9, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
            transferred_air = transfer_mass * self.m_air_cr / crankcase_total
            transferred_fuel = transfer_mass * self.m_fuel_cr / crankcase_total
            transferred_residual = transfer_mass * self.m_residual_cr / crankcase_total
            dm_air_tr = transferred_air / max(dt, 1e-6)
            dm_fuel_tr = transferred_fuel / max(dt, 1e-6)
            dm_burned_tr = transferred_residual / max(dt, 1e-6)
            self.m_air_cr -= transferred_air
            self.m_fuel_cr -= transferred_fuel
            self.m_residual_cr -= transferred_residual
            self.m_air_cyl += transferred_air
            cylinder_wet_fraction = max(0.05, 0.25 - 0.005 * max(0.0, self.T_cyl - T_ATM))
            cylinder_film_added = transferred_fuel * cylinder_wet_fraction
            self.fuel_film_cyl += cylinder_film_added
            self.m_fuel_cyl += transferred_fuel - cylinder_film_added
            self.m_burned_cyl += transferred_residual
        cylinder_evap_rate = 5.0 + 0.04 * max(0.0, self.T_cyl - T_ATM)
        cylinder_evaporated = min(self.fuel_film_cyl, self.fuel_film_cyl * cylinder_evap_rate * dt)
        self.fuel_film_cyl -= cylinder_evaporated
        if not self.fuel_cutoff:
            self.m_fuel_cyl += cylinder_evaporated
        dm_air_exh = 0.0
        dm_fuel_exh = 0.0
        dm_burned_exh = 0.0
        if dm_exh >= 0.0:
            exhaust_mass = min(dm_exh * dt, self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl)
            burned_preference = 0.82 - 0.12 * throttle_factor
            exhausted_burned = min(self.m_burned_cyl, exhaust_mass * burned_preference)
            remaining_exhaust = max(0.0, exhaust_mass - exhausted_burned)
            
            remaining_total = max(1e-9, self.m_air_cyl + self.m_fuel_cyl + (self.m_burned_cyl - exhausted_burned))
            exhausted_fuel = min(self.m_fuel_cyl, remaining_exhaust * (self.m_fuel_cyl / remaining_total))
            exhausted_air = min(self.m_air_cyl, remaining_exhaust * (self.m_air_cyl / remaining_total))
            exhausted_burned += min(self.m_burned_cyl - exhausted_burned, remaining_exhaust * ((self.m_burned_cyl - exhausted_burned) / remaining_total))
            
            dm_air_exh = exhausted_air / max(dt, 1e-6)
            dm_fuel_exh = exhausted_fuel / max(dt, 1e-6)
            dm_burned_exh = exhausted_burned / max(dt, 1e-6)
            self.m_air_cyl -= exhausted_air
            self.m_fuel_cyl -= exhausted_fuel
            self.m_burned_cyl -= exhausted_burned
        else:
            # No ignition or no fuel - reset lambda to neutral
            if self.m_fuel_cyl < 1e-9 or not self.ignition_enabled:
                self.lambda_value = 1.0
            if not self.fuel_cutoff:
                self.m_air_cyl += -dm_exh * dt
        self.m_cyl = self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl
        self.m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        # Guard against zero volumes in mass limit calculations
        v_cyl = max(v_cyl, 1e-9)
        v_cr = max(v_cr, 1e-9)
        min_cyl_mass = MIN_PRESSURE * v_cyl / (R_GAS * max(T_ATM, self.T_cyl))
        min_cr_mass = MIN_CRANKCASE_PRESSURE * v_cr / (R_GAS * max(T_ATM, self.T_cr))
        max_cyl_mass = MAX_CYLINDER_PRESSURE * v_cyl / (R_GAS * max(T_ATM, self.T_cyl))
        max_cr_mass = MAX_CRANKCASE_PRESSURE * v_cr / (R_GAS * max(T_ATM, self.T_cr))
        if self.m_cyl < min_cyl_mass and not self.fuel_cutoff:
            self.m_air_cyl += min_cyl_mass - self.m_cyl
        elif self.m_cyl > max_cyl_mass:
            self.m_air_cyl, self.m_fuel_cyl, self.m_burned_cyl = self.rescale_components(
                self.m_air_cyl,
                self.m_fuel_cyl,
                self.m_burned_cyl,
                target_total=max_cyl_mass,
            )
        self.m_cyl = self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl
        if self.m_cr < min_cr_mass and not self.fuel_cutoff:
            self.m_air_cr += min_cr_mass - self.m_cr
        elif self.m_cr > max_cr_mass:
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr = self.rescale_components(
                self.m_air_cr,
                self.m_fuel_cr,
                self.m_residual_cr,
                target_total=max_cr_mass,
            )
        self.m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        d_v_cyl = self.A_p * dx_dtheta * self.omega * dt
        d_v_cr = -self.A_p * dx_dtheta * self.omega * dt
        
        actual_dm_in = dm_air_in + dm_fuel_in
        actual_dm_tr = dm_air_tr + dm_fuel_tr + dm_burned_tr
        dm_net_cr_step = (actual_dm_in - actual_dm_tr) * dt
        
        h_in_cr_J = T_ATM * actual_dm_in * dt * C_P
        h_out_cr_J = self.T_cr * C_P * actual_dm_tr * dt
        
        d_q_total_cr_J = h_in_cr_J - h_out_cr_J - p_cr * d_v_cr
        m_cv_dT_cr_J = d_q_total_cr_J + self.T_cr * C_V * dm_net_cr_step
        
        m_avg_cr = max(1e-6, self.m_cr - dm_net_cr_step * 0.5)
        self.T_cr = max(T_ATM, self.T_cr + m_cv_dT_cr_J / (m_avg_cr * C_V))
        self.cycle_air_in += max(0.0, dm_air_in) * dt
        self.cycle_air_tr += max(0.0, dm_air_tr) * dt
        self.cycle_air_exh += max(0.0, dm_air_exh) * dt
        self.spark_active = False
        theta_deg = math.degrees(self.theta) % 360.0
        if self.theta < self.last_theta_cross:
            ideal_air_mass = (self.V_d * P_ATM) / (R_GAS * T_ATM)
            self.volumetric_efficiency = self.cycle_air_tr / max(ideal_air_mass, 1e-9)
            fresh_lost = max(0.0, self.cycle_air_exh * 0.25)
            self.trapping_efficiency = max(0.0, self.cycle_air_tr - fresh_lost) / max(self.cycle_air_tr, 1e-9)
        self.last_theta_cross = self.theta
        fresh_charge_mass = self.m_air_cyl + self.m_fuel_cyl
        ignition_window_active = 0 <= self.angle_diff(theta_deg, self.ignition_angle_deg) < 18
        can_ignite = ignition_window_active and not self.combustion_active and x < 0.03 and fresh_charge_mass > 1e-6 and self.ignition_enabled and not self.fuel_cutoff
        if can_ignite:
            self.combustion_active = True
            self.spark_active = True
            self.theta_ign = self.theta
            self.burn_fraction = 0.0
            available_fuel = min(self.m_fuel_cyl, self.m_air_cyl / STOICH_AFR)
            
            actual_fuel_air_ratio = self.m_fuel_cyl / max(1e-9, self.m_air_cyl)
            self.lambda_value = (1.0 / max(1e-9, actual_fuel_air_ratio)) / STOICH_AFR
            
            # Misfire if too lean or too rich
            if available_fuel <= 1e-9 or self.lambda_value > 2.0 or self.lambda_value < 0.5:
                self.combustion_active = False
                self.lambda_value = min(max(self.lambda_value, 0.5), 2.5)  # Cap for display
            else:
                self.combustion_efficiency = self.mixture_efficiency(self.lambda_value) * self.ignition_efficiency()
                turbulence = 0.65 + 0.70 * throttle_factor + 0.25 * min(1.0, abs(self.omega) / 260.0)
                turbulence = max(0.1, turbulence)  # Prevent division by zero
                duration_deg = 55.0 / turbulence
                if self.lambda_value < 0.85:
                    duration_deg *= 1.10
                elif self.lambda_value > 1.10:
                    duration_deg *= 1.25
                # Använd burn_duration_factor för att justera förbränningstid
                duration_deg *= self.burn_duration_factor
                self.burn_duration = math.radians(max(18.0, min(65.0, duration_deg)))
                self.combustible_fuel_mass = available_fuel * min(1.0, 0.70 + 0.30 * self.combustion_efficiency * self.combustion_efficiency)
        d_q_comb = 0.0
        if self.combustion_active:
            # Check if we still have fuel to burn
            if self.m_fuel_cyl < 1e-9 or not self.ignition_enabled or self.fuel_cutoff:
                self.combustion_active = False
                self.burn_fraction = 0.0
            else:
                dtheta = (self.theta - self.theta_ign) % (2 * math.pi)
                if dtheta < self.burn_duration:
                    phase = min(1.0, dtheta / max(self.burn_duration, 1e-6))
                    new_burn_fraction = 1.0 - math.exp(-5.8 * (phase ** 3.0))
                    delta_burn_fraction = max(0.0, new_burn_fraction - self.burn_fraction)
                    fuel_burned = min(self.combustible_fuel_mass * delta_burn_fraction, self.m_fuel_cyl)
                    air_consumed = fuel_burned * STOICH_AFR
                    if air_consumed > self.m_air_cyl:
                        air_consumed = self.m_air_cyl
                        fuel_burned = air_consumed / STOICH_AFR
                    self.m_fuel_cyl -= fuel_burned
                    self.m_air_cyl -= air_consumed
                    self.m_burned_cyl += fuel_burned + air_consumed
                    d_q_comb = fuel_burned * FUEL_LHV
                    self.burn_fraction = new_burn_fraction
                else:
                    self.combustion_active = False
                    self.burn_fraction = 1.0
        self.m_cyl = self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl
        self.x_b_cyl = self.m_burned_cyl / max(self.m_cyl, 1e-9)
        
        # Energy balance for temperature change using CLAMPED actual mass flows
        actual_dm_tr = dm_air_tr + dm_fuel_tr + dm_burned_tr
        
        # Determine actual exhaust flows (can be positive or negative)
        if dm_exh >= 0.0:
            actual_dm_exh_out = dm_air_exh + dm_fuel_exh + dm_burned_exh
            actual_dm_exh_in = 0.0
        else:
            actual_dm_exh_out = 0.0
            actual_dm_exh_in = -dm_exh if not self.fuel_cutoff else 0.0
            
        dm_net_cyl_step = (actual_dm_tr - actual_dm_exh_out + actual_dm_exh_in) * dt
        if not self.fuel_cutoff:
             dm_net_cyl_step += cylinder_evaporated
             
        h_in_tr_J = self.T_cr * C_P * actual_dm_tr * dt
        h_in_exh_backflow_J = self.T_cyl * 0.9 * C_P * actual_dm_exh_in * dt
        h_out_exh_J = self.T_cyl * C_P * actual_dm_exh_out * dt
        
        d_q_total_J = d_q_comb + h_in_tr_J + h_in_exh_backflow_J - h_out_exh_J - p_cyl * d_v_cyl
        
        # NOTE FOR DEBUGGING: We will save d_q_comb to self.last_d_q_comb
        self.last_d_q_comb = d_q_comb
        
        # Add the internal energy change due to mass change
        m_cv_dT_J = d_q_total_J + self.T_cyl * C_V * dm_net_cyl_step
        
        # Use average mass during the step to avoid division by near-zero if cylinder empties
        m_avg = max(1e-6, self.m_cyl - dm_net_cyl_step * 0.5)
        self.T_cyl = max(T_ATM, self.T_cyl + m_cv_dT_J / (m_avg * C_V))
        self.T_cyl -= (self.T_cyl - 350) * 15.0 * dt
        self.T_cr -= (self.T_cr - 300) * 5.0 * dt
        self.T_cyl = min(max(T_ATM, self.T_cyl), 3000.0)
        self.T_cr = min(max(T_ATM, self.T_cr), 500.0)
        # Guard against zero volumes in final pressure calculations
        v_cyl = max(v_cyl, 1e-9)
        v_cr = max(v_cr, 1e-9)
        p_cyl = min(MAX_CYLINDER_PRESSURE, max(MIN_PRESSURE, self.m_cyl * R_GAS * self.T_cyl / v_cyl))
        p_cr = min(MAX_CRANKCASE_PRESSURE, max(MIN_CRANKCASE_PRESSURE, self.m_cr * R_GAS * self.T_cr / v_cr))
        f_gas = (p_cyl - P_ATM) * self.A_p
        f_cr = (p_cr - P_ATM) * self.A_p
        torque = (f_gas - f_cr) * dx_dtheta
        
        step_dtheta = self.omega * dt
        self.cycle_work += torque * step_dtheta
        
        starter_torque = self.starter_torque if (starter_active and self.omega < 100.0) else 0.0
        
        # Pumping drag increases with square of RPM, friction is relatively constant with slight increase
        pumping_drag = self.omega * 0.008 + 0.000008 * self.omega * self.omega + (1.0 - self.throttle) * 2.0
        # Extra braking when fuel is cut off - engine should stop quickly (but not when starter is active)
        extra_brake = 8.0 if self.fuel_cutoff and not starter_active else 0.0
        # Använd trimnings-faktorer för friktion
        effective_friction = self.friction * self.friction_factor
        net_torque = torque + starter_torque - effective_friction - pumping_drag - extra_brake
        # Guard against zero moment of inertia, använd inertia_multiplier
        I_engine = max(self.I_engine * self.inertia_multiplier, 1e-6)
        self.omega += (net_torque / I_engine) * dt
        if self.omega < 40.0:
            # Only apply idle assistance if engine should be running
            if self.ignition_enabled and not self.fuel_cutoff:
                self.omega += (self.idle_omega_target - self.omega) * 3.5 * dt
                self.theta = (self.theta + math.radians(6.0) * dt * 60.0) % (2 * math.pi)
        self.omega = max(0.0, min(self.omega, 1400.0))  # Max ~13300 RPM
        self.theta = (self.theta + self.omega * dt) % (2 * math.pi)
        
        # Calculate EMA values for display
        rpm = self.omega * 30 / math.pi
        self.rpm_ema = self.rpm_ema * 0.98 + rpm * 0.02
        if self.theta < self.last_theta_cross:
            # Net cycle torque is work per cycle / 2 pi
            self.last_cycle_torque = self.cycle_work / (2 * math.pi) - self.friction - pumping_drag
            self.cycle_work = 0.0
            self.cycle_air_in = 0.0
            self.cycle_air_tr = 0.0
            self.cycle_air_exh = 0.0
            
            self.torque_ema = self.torque_ema * 0.80 + self.last_cycle_torque * 0.20
            # Power in kW = Torque (Nm) * Omega (rad/s) / 1000 * mechanical_efficiency
            power_kw = max(0.0, (self.torque_ema * self.omega) / 1000.0 * self.mechanical_efficiency)
            self.power_ema = self.power_ema * 0.80 + power_kw * 0.20
            
        self.last_theta_cross = self.theta
        
        # Validate state before returning
        if not self.validate_state():
            raise RuntimeError("Physics state validation failed - detected NaN/infinity or invalid values")

        return EngineSnapshot(
            x=x,
            p_cyl=p_cyl,
            p_cr=p_cr,
            p_exh_pipe=self.p_pipe,
            a_exh=a_exh,
            a_tr=a_tr,
            a_in=a_in,
            rpm=self.rpm_ema,
            torque=self.torque_ema,
            power_kw=self.power_ema,
            dm_exh=dm_exh,
            dm_tr=dm_tr,
            dm_in=dm_in,
            dm_air_in=dm_air_in,
            dm_fuel_in=dm_fuel_in,
            dm_air_tr=dm_air_tr,
            dm_fuel_tr=dm_fuel_tr,
            dm_burned_tr=dm_burned_tr,
            dm_air_exh=dm_air_exh,
            dm_fuel_exh=dm_fuel_exh,
            dm_burned_exh=dm_burned_exh,
            volumetric_efficiency=self.volumetric_efficiency,
            trapping_efficiency=self.trapping_efficiency,
        )
