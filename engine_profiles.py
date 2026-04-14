"""
Engine Profiles Database — 2-stroke moped engines
=================================================
Profiler för de vanligaste 2-taktsmotorerna som trimmas idag.
Parametrarna mappar direkt mot EnginePhysics i physics.py.

Porttimings anges i grader ATDC (After Top Dead Center).
Port-höjder (x_exh, x_tr) anges som kolvvandring från BDC i meter.

Källor:
  - Yamaha Aerox service manual (YQ50), Maxiscoot tech sheets
  - Minarelli AM6 workshop manual
  - Stage6, Malossi, Polini produktdata
  - Aprilia Forum mätdata och portjämförelser
  - 50factory.com tekniska datablad

Version 3.1: JSON-baserad profil-databas med 22 stock + tuned profiler.
"""

import math
import json
import os

__all__ = [
    # Profile data
    'ALL_PROFILES', 'BASE_PROFILE',
    # Legacy profiles
    'AM6_STOCK', 'AM6_STAGE6_RT_70', 'AM6_MALOSSI_MHR_70', 'AM6_BIGBORE_80', 'AM6_LONGSTROKE_78',
    'AM3_HORIZONTAL_STOCK', 'AM3_MALOSSI_SPORT_70',
    'AM_HORIZONTAL_LC_STOCK', 'AM_HORIZONTAL_LC_DERESTRICTED', 'AM_HORIZONTAL_LC_MALOSSI_MHR_70',
    'PIAGGIO_HIPER2_STOCK', 'PIAGGIO_POLINI_70', 'PIAGGIO_MALOSSI_70',
    'DERBI_EBE_STOCK', 'DERBI_POLINI_70', 'DERBI_D50B_STOCK',
    # JSON loading functions
    'get_profiles_json_path', 'load_json_profiles', 'get_all_json_profile_keys', 'get_json_profile_metadata',
    # Profile application functions
    'apply_profile', 'apply_json_profile', 'list_profiles', 'list_all_profiles',
    # Utility functions
    'port_height_from_timing',
]

# ---------------------------------------------------------------------------
# JSON Profile Loading (v3.1)
# ---------------------------------------------------------------------------

def get_profiles_json_path() -> str:
    """Get the path to the engine_profiles.json file."""
    # Look in same directory as this module
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_dir, "engine_profiles.json")


def load_json_profiles() -> dict:
    """
    Load engine profiles from engine_profiles.json.
    Returns a dict of {profile_key: profile_data}.
    """
    json_path = get_profiles_json_path()
    if not os.path.exists(json_path):
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('profiles', {})
    except (json.JSONDecodeError, IOError):
        return {}


def get_all_json_profile_keys() -> list:
    """Return a list of all JSON profile keys."""
    return list(load_json_profiles().keys())


def get_json_profile_metadata(profile_key: str) -> dict:
    """
    Get metadata for a JSON profile (port_timing, trim_parts, notes, etc.)
    Returns empty dict if profile not found.
    """
    profiles = load_json_profiles()
    prof = profiles.get(profile_key, {})
    return {
        'port_timing_deg': prof.get('port_timing_deg', {}),
        'trim_parts': prof.get('trim_parts', []),
        'notes': prof.get('notes', ''),
        'research_sources': prof.get('research_sources', []),
        'cooling': prof.get('cooling', 'air'),
        'stock_power_kw': prof.get('stock_power_kw', 0),
        'stock_rpm_peak': prof.get('stock_rpm_peak', 0),
        'carburetor': prof.get('carburetor', ''),
    }


# ---------------------------------------------------------------------------
# Hjälpfunktion: konvertera porttiminig till pistonvandring (x)
# ---------------------------------------------------------------------------

def port_height_from_timing(
    exhaust_deg_atdc: float,
    stroke: float,
    conrod: float
) -> float:
    """
    Räknar ut pistonvandring (x) från BDC när porten öppnar.
    exhaust_deg_atdc = vinkeln ATDC (t.ex. 90 = 90 grader efter TDC)
    Returnerar x i meter (hur långt kolvkanten är ovanför BDC).
    """
    R = stroke / 2.0
    theta = math.radians(exhaust_deg_atdc)
    beta_arg = max(-1.0, min(1.0, R / conrod * math.sin(theta)))
    beta = math.asin(beta_arg)
    x_from_tdc = R * (1 - math.cos(theta)) + conrod * (1 - math.cos(beta))
    x_from_bdc = stroke - x_from_tdc
    return x_from_bdc


# ---------------------------------------------------------------------------
# Standardprofil — används som mall
# ---------------------------------------------------------------------------

BASE_PROFILE = {
    # Motorgeometri
    "B": 0.040,              # Borrning (m)
    "stroke": 0.039,         # Slag (m)
    "R": 0.0195,             # Halvt slag (m)
    "L": 0.085,              # Vevstakelängd (m)
    "compression_ratio": 12.0,

    # Vevhus
    "V_cr_min_factor": 1.8,  # Vevhusvolym = V_d * faktor

    # Tröghet & friktion
    "I_engine": 0.008,
    "friction": 0.65,

    # Portgeometri (meter från BDC)
    "x_exh": 0.0240,
    "x_tr": 0.0340,
    "w_exh": 0.038,
    "w_tr": 0.032,

    # Reed valve area (m²)
    "A_in_max": 0.00120,

    # Tändning
    "ignition_angle_deg": 340,

    # Expansionskammare / avgasstöt
    "pipe_resonance_freq": 120.0,   # Hz
    "pipe_q_factor": 2.5,

    # Metadata
    "cooling": "air",
    "stock_power_kw": 3.0,
    "stock_rpm_peak": 6500,
    "carburetor": "Dell'Orto SHA 14/12",
    "transmission": "manual",
    "notes": "",
}


# ===========================================================================
# MINARELLI AM6 — STÅENDE (VERTIKAL), VATTENKYLDA
# Används i: Aprilia RS50, MBK X-Power, Yamaha TZR50, Derbi GPR50
# ===========================================================================

AM6_STOCK = {
    **BASE_PROFILE,
    "name": "Minarelli AM6 Stock 50cc",
    # Geometri — OEM: 40,3mm × 39mm = 49,7cc
    "B": 0.0403,
    "stroke": 0.039,
    "R": 0.0195,
    "L": 0.085,              # OEM vevstake 85mm
    "compression_ratio": 12.0,
    # Vevhus
    "V_cr_min_factor": 1.8,
    "I_engine": 0.009,
    "friction": 0.70,
    # Portar (stock AM6: exh öppnar 88° ATDC → 176° duration, tr öppnar 60° före BDC → 120° duration)
    # x_exh = kolvvandring vid avgasportöppning ≈ 88° ATDC, slag=39mm, stav=85mm
    "x_exh": port_height_from_timing(88, 0.039, 0.085),   # ≈ 0.0225 m
    "x_tr":  port_height_from_timing(60, 0.039, 0.085),   # ≈ 0.0322 m
    "w_exh": 0.040,
    "w_tr":  0.034,
    "A_in_max": 0.00130,
    "ignition_angle_deg": 340,
    # Expansionskammare
    "pipe_resonance_freq": 125.0,   # ~7500 RPM
    "pipe_q_factor": 2.5,
    # Metadata
    "cooling": "liquid",
    "stock_power_kw": 4.0,
    "stock_rpm_peak": 7500,
    "carburetor": "Dell'Orto PHBG 17.5",
    "transmission": "manual 6-vxl",
    "notes": "Aprilia RS50, MBK X-Power, Yamaha TZR50, Derbi GPR50. "
              "Port timing: exh 176°, tr 120°. Blowdown 28°.",
}

# --- TRIMDEL: Stage6 R/T 70cc kit (47,6mm borrning, 6 transferportar, bridged exhaust)
# Port timing 190°/130° (stage6-racing.com)
AM6_STAGE6_RT_70 = {
    **AM6_STOCK,
    "name": "Minarelli AM6 Stage6 R/T 70cc",
    "B": 0.0476,
    "stroke": 0.039,          # originalslag
    "R": 0.0195,
    "L": 0.085,
    "compression_ratio": 14.5,
    "x_exh": port_height_from_timing(95, 0.039, 0.085),   # 190° duration → öppnar 95° ATDC
    "x_tr":  port_height_from_timing(65, 0.039, 0.085),   # 130° duration → öppnar 65° ATDC
    "w_exh": 0.052,           # bridged exhaust — bredare men delad
    "w_tr":  0.042,           # 6 transferportar totalt
    "A_in_max": 0.00160,
    "pipe_resonance_freq": 167.0,   # ~10000 RPM
    "pipe_q_factor": 3.5,
    "ignition_angle_deg": 344,
    "stock_power_kw": 12.0,
    "stock_rpm_peak": 10000,
    "carburetor": "Dell'Orto PHBG 21 / Keihin PWK 24",
    "notes": "Stage6 R/T 70 kit. 6 transferportar, bridged exhaust. "
              "Port timing: exh 190°, tr 130°. Kräver expansionskammare Stage6 70-80 R/T.",
}

# --- TRIMDEL: Malossi MHR Team Testa Rossa 70cc (47,6mm, 7 transferportar, bridged exhaust)
# Port timing 192°/132° (malossi.it, bekräftat på scooterforum.net)
AM6_MALOSSI_MHR_70 = {
    **AM6_STOCK,
    "name": "Minarelli AM6 Malossi MHR Team 70cc",
    "B": 0.0476,
    "stroke": 0.039,
    "R": 0.0195,
    "L": 0.085,
    "compression_ratio": 15.5,
    "x_exh": port_height_from_timing(96, 0.039, 0.085),   # 192° duration
    "x_tr":  port_height_from_timing(66, 0.039, 0.085),   # 132° duration
    "w_exh": 0.054,           # 7 portar inkl bridged exh
    "w_tr":  0.045,
    "A_in_max": 0.00170,
    "pipe_resonance_freq": 175.0,   # ~10500 RPM
    "pipe_q_factor": 3.8,
    "ignition_angle_deg": 345,
    "stock_power_kw": 15.0,
    "stock_rpm_peak": 10500,
    "carburetor": "Dell'Orto PHBG 21 / VHST 28",
    "notes": "Malossi MHR Testa Rossa. 7 transferportar, bridged exhaust, Nikasil. "
              "Port timing: exh 192°, tr 132°. Kräver racingvevaxel och expansionskammare.",
}

# --- TRIMDEL: BigBore AM6 80cc kit (50mm borrning, Barikit/Polini)
# Bore 50mm, slag original 39mm → 76,6cc
AM6_BIGBORE_80 = {
    **AM6_STOCK,
    "name": "Minarelli AM6 BigBore 80cc (50mm)",
    "B": 0.050,
    "stroke": 0.039,
    "R": 0.0195,
    "L": 0.085,
    "compression_ratio": 14.0,
    "x_exh": port_height_from_timing(94, 0.039, 0.085),
    "x_tr":  port_height_from_timing(64, 0.039, 0.085),
    "w_exh": 0.056,
    "w_tr":  0.048,
    "A_in_max": 0.00180,
    "pipe_resonance_freq": 183.0,
    "pipe_q_factor": 3.5,
    "ignition_angle_deg": 343,
    "stock_power_kw": 18.0,
    "stock_rpm_peak": 11000,
    "carburetor": "Keihin PWK 28 / Dell'Orto VHST 28",
    "notes": "BigBore 50mm bore, 76,6cc. Barikit/Polini/Stage6. "
              "Kräver modifierat vevhus och anpassad expansionskammare.",
}

# --- TRIMDEL: AM6 med lång vevstake 47mm slag (Stage6 R/T crankshaft)
# Vevstake 90mm, slag 44mm → ca 78cc med 47,6mm borrning
AM6_LONGSTROKE_78 = {
    **AM6_STAGE6_RT_70,
    "name": "Minarelli AM6 Stage6 Longstroke 78cc (47mm slag)",
    "stroke": 0.044,
    "R": 0.022,
    "L": 0.090,               # Stage6 R/T 90mm conrod
    "compression_ratio": 13.5,
    "x_exh": port_height_from_timing(95, 0.044, 0.090),
    "x_tr":  port_height_from_timing(65, 0.044, 0.090),
    "pipe_resonance_freq": 155.0,
    "stock_power_kw": 14.0,
    "stock_rpm_peak": 9300,
    "notes": "Stage6 vevaxel 44mm slag / 90mm stav + RT 70cc cylinder. "
              "Ger bredare effektband vs kortslag. Ca 78cc.",
}


# ===========================================================================
# MINARELLI HORISONTELL — LIGGANDE, LUFTKYLD
# Används i: Peugeot 103, MBK 51, Yamaha Jog/BW, Aprilia SR50 AC
# ===========================================================================

AM3_HORIZONTAL_STOCK = {
    **BASE_PROFILE,
    "name": "Minarelli AM3/AM5 Horisontell Luftkyld Stock 50cc",
    "B": 0.040,
    "stroke": 0.039,
    "R": 0.0195,
    "L": 0.083,
    # Stock port timing: exh ~83° ATDC (166°), tr ~58° ATDC (116°)
    "x_exh": port_height_from_timing(83, 0.039, 0.083),
    "x_tr":  port_height_from_timing(58, 0.039, 0.083),
    "w_exh": 0.036,
    "w_tr":  0.030,
    "A_in_max": 0.00110,
    "compression_ratio": 9.5,
    "V_cr_min_factor": 2.0,
    "I_engine": 0.008,
    "friction": 0.62,
    "ignition_angle_deg": 338,
    "pipe_resonance_freq": 100.0,   # ~6000 RPM
    "pipe_q_factor": 2.0,
    "cooling": "air",
    "stock_power_kw": 3.0,
    "stock_rpm_peak": 6000,
    "carburetor": "Dell'Orto SHA 14/12",
    "transmission": "automatisk CVT / variator",
    "notes": "Peugeot 103 SP/MVL, MBK 51, Yamaha Jog 50, Yamaha BW 50. "
              "Luftkyld liggande motor. Reed valve mot vevhus.",
}

# --- TRIMDEL: Malossi Sport 70cc liggande luftkyld (47mm, cast iron, 6 portar)
AM3_MALOSSI_SPORT_70 = {
    **AM3_HORIZONTAL_STOCK,
    "name": "Minarelli Horisontell Malossi Sport 70cc",
    "B": 0.047,
    "compression_ratio": 12.0,
    "x_exh": port_height_from_timing(88, 0.039, 0.083),
    "x_tr":  port_height_from_timing(62, 0.039, 0.083),
    "w_exh": 0.044,
    "w_tr":  0.038,
    "A_in_max": 0.00140,
    "pipe_resonance_freq": 133.0,   # ~8000 RPM
    "pipe_q_factor": 3.0,
    "ignition_angle_deg": 341,
    "stock_power_kw": 8.0,
    "stock_rpm_peak": 8000,
    "carburetor": "Dell'Orto PHBG 19 / SHA 15",
    "notes": "Malossi 317083 cast iron 70cc kit. 6 portar, 2 segments. "
              "Passar Yamaha Jog, MBK, Peugeot 103 med horisontell Minarelli.",
}

# MINARELLI HORISONTELL — LIGGANDE, VATTENKYLDA (LC)
# Används i: Yamaha Aerox, MBK Nitro, Malaguti F12/F15

AM_HORIZONTAL_LC_STOCK = {
    **BASE_PROFILE,
    "name": "Minarelli Horisontell LC Stock 50cc (Aerox/Nitro)",
    # Yamaha Aerox: 40mm × 39,2mm = 49,2cc
    "B": 0.040,
    "stroke": 0.0392,
    "R": 0.0196,
    "L": 0.084,
    "compression_ratio": 7.9,    # Begränsad EU-version (kat)
    # Stock port timing likvärdig AM6 horisontell: exh ~88°, tr ~60°
    "x_exh": port_height_from_timing(88, 0.0392, 0.084),
    "x_tr":  port_height_from_timing(60, 0.0392, 0.084),
    "w_exh": 0.038,
    "w_tr":  0.032,
    "A_in_max": 0.00125,
    "V_cr_min_factor": 1.85,
    "I_engine": 0.007,
    "friction": 0.60,
    "ignition_angle_deg": 336,    # Retarderad av begränsning
    "pipe_resonance_freq": 112.0, # ~6700 RPM (stock med kat)
    "pipe_q_factor": 2.2,
    "cooling": "liquid",
    "stock_power_kw": 2.5,        # Begränsad version
    "stock_rpm_peak": 6750,
    "carburetor": "Gurtner PY-12 / Dell'Orto 12",
    "transmission": "automatisk CVT",
    "notes": "Yamaha Aerox 50 LC (1997-2012), MBK Nitro 50 LC, Malaguti F12/F15. "
              "Begränsad stock: CR 7,9:1, retarderad tändning, liten förgasare. "
              "Spark plug: NGK BR8HS. Oljeseparation: separat tank 1,4L.",
}

# --- Aerox/Nitro derestriktad (avlägsnad begränsare, original cylinder)
AM_HORIZONTAL_LC_DERESTRICTED = {
    **AM_HORIZONTAL_LC_STOCK,
    "name": "Minarelli Horisontell LC Derestriktad",
    "compression_ratio": 12.0,   # Återställd kompression (borttagen spacer)
    "ignition_angle_deg": 340,   # Återställd tändning
    "pipe_resonance_freq": 120.0,
    "stock_power_kw": 4.0,
    "stock_rpm_peak": 7500,
    "carburetor": "Dell'Orto PHBG 17.5",
    "notes": "Aerox/Nitro med avlägsnad begränsare: variator-begränsare borttagen, "
              "kompressionsspacer borttagen, CDI bytt mot fri tändkurva. "
              "Reed valve block: VL18 eller Malossi dellorto reed.",
}

# --- TRIMDEL: Malossi MHR Racing 70cc vattenkylda horisontell (47,6mm, Aerox/Nitro)
AM_HORIZONTAL_LC_MALOSSI_MHR_70 = {
    **AM_HORIZONTAL_LC_DERESTRICTED,
    "name": "Minarelli Horiz. LC Malossi MHR Racing 70cc (Aerox)",
    "B": 0.0476,
    "stroke": 0.0392,
    "R": 0.0196,
    "L": 0.085,
    "compression_ratio": 15.5,
    "x_exh": port_height_from_timing(96, 0.0392, 0.085),  # 192° duration
    "x_tr":  port_height_from_timing(66, 0.0392, 0.085),  # 132° duration
    "w_exh": 0.054,
    "w_tr":  0.046,
    "A_in_max": 0.00170,
    "pipe_resonance_freq": 175.0,
    "pipe_q_factor": 3.8,
    "ignition_angle_deg": 345,
    "stock_power_kw": 16.0,
    "stock_rpm_peak": 10500,
    "carburetor": "Dell'Orto PHBG 21 / VHST 28",
    "notes": "Malossi MHR Racing 70cc LC för Yamaha Aerox, MBK Nitro, Malaguti F12/F15. "
              "Topmodell. Kräver racingvevaxel och expansionskammare.",
}


# ===========================================================================
# PIAGGIO Hi-PER2 (C9) — Luftkyld
# Används i: Piaggio Zip 50, Fly 50, Typhoon 50, Gilera Runner 50, Vespa ET2
# ===========================================================================

PIAGGIO_HIPER2_STOCK = {
    **BASE_PROFILE,
    "name": "Piaggio Hi-PER2 (C9) Stock 50cc",
    # 39mm × 41,8mm = 49,4cc
    "B": 0.039,
    "stroke": 0.0418,
    "R": 0.0209,
    "L": 0.088,
    "compression_ratio": 11.5,
    # Stock port timing Piaggio C9: exh ~86°, tr ~60°
    "x_exh": port_height_from_timing(86, 0.0418, 0.088),
    "x_tr":  port_height_from_timing(60, 0.0418, 0.088),
    "w_exh": 0.036,
    "w_tr":  0.030,
    "A_in_max": 0.00105,
    "V_cr_min_factor": 1.9,
    "I_engine": 0.007,
    "friction": 0.60,
    "ignition_angle_deg": 338,
    "pipe_resonance_freq": 112.0,   # ~6700 RPM
    "pipe_q_factor": 2.2,
    "cooling": "air",
    "stock_power_kw": 3.3,
    "stock_rpm_peak": 6700,
    "carburetor": "Dell'Orto PHVA 17.5",
    "transmission": "automatisk CVT",
    "notes": "Piaggio Zip 50 2T, Fly 50, Typhoon 50, Gilera Runner 50, Vespa ET2. "
              "Max torque 4,3 Nm vid 6500 RPM. Automatisk CVT.",
}

# --- TRIMDEL: Polini Sport 70cc för Piaggio C9 (47mm)
PIAGGIO_POLINI_70 = {
    **PIAGGIO_HIPER2_STOCK,
    "name": "Piaggio C9 Polini Sport 70cc",
    "B": 0.047,
    "compression_ratio": 13.5,
    "x_exh": port_height_from_timing(90, 0.0418, 0.088),
    "x_tr":  port_height_from_timing(62, 0.0418, 0.088),
    "w_exh": 0.043,
    "w_tr":  0.037,
    "A_in_max": 0.00145,
    "pipe_resonance_freq": 140.0,
    "pipe_q_factor": 3.0,
    "ignition_angle_deg": 341,
    "stock_power_kw": 9.0,
    "stock_rpm_peak": 8500,
    "carburetor": "Dell'Orto PHVA 19 / PHBG 19",
    "notes": "Polini Sport 70cc kit för Piaggio Hi-PER2. "
              "Passar Zip 50, Fly 50, Typhoon 50, Gilera Runner 50.",
}

# --- TRIMDEL: Malossi Sport 70cc för Piaggio C9 (cast iron 47mm)
PIAGGIO_MALOSSI_70 = {
    **PIAGGIO_HIPER2_STOCK,
    "name": "Piaggio C9 Malossi Sport 70cc",
    "B": 0.047,
    "compression_ratio": 12.5,
    "x_exh": port_height_from_timing(88, 0.0418, 0.088),
    "x_tr":  port_height_from_timing(61, 0.0418, 0.088),
    "w_exh": 0.042,
    "w_tr":  0.036,
    "A_in_max": 0.00140,
    "pipe_resonance_freq": 133.0,
    "pipe_q_factor": 3.0,
    "ignition_angle_deg": 340,
    "stock_power_kw": 8.0,
    "stock_rpm_peak": 8000,
    "carburetor": "Dell'Orto PHVA 19",
    "notes": "Malossi cast iron 70cc för Piaggio C9. Bra gatuversion med bred effektkurva.",
}


# ===========================================================================
# DERBI EBE/EBS — Luftkyld
# Används i: Derbi Senda 50, Derbi Variant Start, Gilera SMT 50, Aprilia RX/SX 50
# ===========================================================================

DERBI_EBE_STOCK = {
    **BASE_PROFILE,
    "name": "Derbi EBE/EBS Stock 50cc",
    # 39,88mm × 40mm = 49,76cc
    "B": 0.03988,
    "stroke": 0.040,
    "R": 0.020,
    "L": 0.086,
    "compression_ratio": 11.5,
    # Port timing EBE/EBS: exh ~85° ATDC (170°), tr ~58° (116°)
    "x_exh": port_height_from_timing(85, 0.040, 0.086),
    "x_tr":  port_height_from_timing(58, 0.040, 0.086),
    "w_exh": 0.037,
    "w_tr":  0.031,
    "A_in_max": 0.00110,
    "V_cr_min_factor": 1.85,
    "I_engine": 0.008,
    "friction": 0.65,
    "ignition_angle_deg": 340,
    "pipe_resonance_freq": 105.0,   # ~6300 RPM
    "pipe_q_factor": 2.2,
    "cooling": "air",
    "stock_power_kw": 3.0,
    "stock_rpm_peak": 6300,
    "carburetor": "SHA Ø12mm / Gurtner 14mm",
    "transmission": "manual 6-vxl",
    "notes": "Derbi Senda 50, Derbi Variant Start, Gilera SMT 50, Aprilia RX 50. "
              "Reed valve direkt mot vevhus. Kick-start.",
}

# --- TRIMDEL: Polini 70cc för Derbi EBE/EBS
DERBI_POLINI_70 = {
    **DERBI_EBE_STOCK,
    "name": "Derbi EBE/EBS Polini Sport 70cc",
    "B": 0.047,
    "compression_ratio": 13.0,
    "x_exh": port_height_from_timing(89, 0.040, 0.086),
    "x_tr":  port_height_from_timing(62, 0.040, 0.086),
    "w_exh": 0.043,
    "w_tr":  0.037,
    "A_in_max": 0.00145,
    "pipe_resonance_freq": 135.0,
    "pipe_q_factor": 3.0,
    "ignition_angle_deg": 342,
    "stock_power_kw": 9.5,
    "stock_rpm_peak": 8100,
    "carburetor": "Dell'Orto PHBG 19 / PHBL 25",
    "notes": "Polini Sport 70cc för Derbi EBE/EBS. Passar Senda, Variant.",
}


# ===========================================================================
# DERBI D50B0 (Post-2005) — Luftkyld
# Ny generation Derbi-motor. Används i Derbi Senda från 2005+
# ===========================================================================

DERBI_D50B_STOCK = {
    **BASE_PROFILE,
    "name": "Derbi D50B0 Stock 50cc (2005+)",
    # 40mm × 39,6mm = 49,9cc
    "B": 0.040,
    "stroke": 0.0396,
    "R": 0.0198,
    "L": 0.086,
    "compression_ratio": 11.8,
    "x_exh": port_height_from_timing(86, 0.0396, 0.086),
    "x_tr":  port_height_from_timing(59, 0.0396, 0.086),
    "w_exh": 0.038,
    "w_tr":  0.032,
    "A_in_max": 0.00115,
    "V_cr_min_factor": 1.85,
    "I_engine": 0.008,
    "friction": 0.65,
    "ignition_angle_deg": 340,
    "pipe_resonance_freq": 108.0,
    "pipe_q_factor": 2.2,
    "cooling": "air",
    "stock_power_kw": 3.2,
    "stock_rpm_peak": 6500,
    "carburetor": "Dell'Orto SHA 14/12",
    "transmission": "manual 6-vxl",
    "notes": "Derbi Senda 50 från 2005+. Uppgraderad motor vs EBE/EBS.",
}


# ===========================================================================
# KATALOG — alla profiler indexerade
# ===========================================================================

ALL_PROFILES = {
    # AM6 vertikal vattenkylda
    "am6_stock":                AM6_STOCK,
    "am6_stage6_rt_70":         AM6_STAGE6_RT_70,
    "am6_malossi_mhr_70":       AM6_MALOSSI_MHR_70,
    "am6_bigbore_80":           AM6_BIGBORE_80,
    "am6_longstroke_78":        AM6_LONGSTROKE_78,

    # Minarelli horisontell luftkyld
    "am3_horizontal_stock":     AM3_HORIZONTAL_STOCK,
    "am3_malossi_sport_70":     AM3_MALOSSI_SPORT_70,

    # Minarelli horisontell vattenkylad (Aerox/Nitro)
    "aerox_lc_stock":           AM_HORIZONTAL_LC_STOCK,
    "aerox_lc_derestricted":    AM_HORIZONTAL_LC_DERESTRICTED,
    "aerox_lc_malossi_mhr_70":  AM_HORIZONTAL_LC_MALOSSI_MHR_70,

    # Piaggio Hi-PER2 (C9)
    "piaggio_c9_stock":         PIAGGIO_HIPER2_STOCK,
    "piaggio_c9_polini_70":     PIAGGIO_POLINI_70,
    "piaggio_c9_malossi_70":    PIAGGIO_MALOSSI_70,

    # Derbi EBE/EBS
    "derbi_ebe_stock":          DERBI_EBE_STOCK,
    "derbi_ebe_polini_70":      DERBI_POLINI_70,

    # Derbi D50B0
    "derbi_d50b_stock":         DERBI_D50B_STOCK,
}


# ===========================================================================
# Loader — applicera profil på EnginePhysics
# ===========================================================================

def _resolve_profile(profile_key: str) -> tuple[dict, str]:
    """
    Resolve a profile key to profile data.
    Checks legacy ALL_PROFILES first, then falls back to JSON profiles.
    Returns (profile_data, source) where source is 'legacy' or 'json'.
    Raises KeyError if not found.
    """
    if profile_key in ALL_PROFILES:
        return ALL_PROFILES[profile_key], 'legacy'

    json_profiles = load_json_profiles()
    if profile_key in json_profiles:
        return json_profiles[profile_key], 'json'

    raise KeyError(f"Profile '{profile_key}' not found in legacy or JSON profiles")


def apply_profile(engine, profile_key: str) -> None:
    """
    Applicera en motorprofil på ett EnginePhysics-objekt.
    Searches legacy ALL_PROFILES first, then falls back to JSON profiles.

    Exempel:
        from engine_profiles import apply_profile
        engine = EnginePhysics()
        apply_profile(engine, "am6_stage6_rt_70")  # legacy key
        apply_profile(engine, "am6_stock_vertical")  # JSON key (v3.1)
    """
    profile, source = _resolve_profile(profile_key)

    # Map profile values to engine physics - supports both legacy and JSON formats
    engine.B = profile["B"]
    engine.R = profile["stroke"] / 2.0
    engine.L = profile["L"]
    engine.A_p = math.pi * (engine.B / 2) ** 2
    engine.V_d = engine.A_p * 2 * engine.R

    cr = profile["compression_ratio"]
    engine.V_c = engine.V_d / (cr - 1.0)

    engine.V_cr_min = engine.V_d * profile["V_cr_min_factor"]
    engine.I_engine = profile["I_engine"]
    engine.friction = profile["friction"]

    engine.x_exh = profile["x_exh"]
    engine.x_tr  = profile["x_tr"]
    engine.w_exh = profile["w_exh"]
    engine.w_tr  = profile["w_tr"]
    engine.A_in_max = profile["A_in_max"]

    engine.ignition_angle_deg = profile["ignition_angle_deg"]
    engine.pipe_resonance_freq = profile["pipe_resonance_freq"]
    engine.pipe_q_factor = profile.get("pipe_q_factor", 2.5)

    # Återinitiera massor baserat på ny volym
    from physics import P_ATM, R_GAS, T_ATM
    engine.T_cyl = T_ATM
    engine.T_cr  = T_ATM
    
    # Set crankcase mass components first (to avoid setter issues)
    engine.m_fuel_cr = 0.0
    engine.m_residual_cr = 0.0
    engine.m_air_cr = engine.V_cr_min * P_ATM / (R_GAS * T_ATM)
    
    # Set cylinder mass components first
    engine.m_fuel_cyl = 0.0
    engine.m_burned_cyl = 0.0
    engine.m_air_cyl = engine.V_c * P_ATM / (R_GAS * T_ATM)
    
    # Now set the total properties (for backward compatibility)
    engine.m_cyl = engine.m_air_cyl + engine.m_fuel_cyl + engine.m_burned_cyl
    engine.m_cr = engine.m_air_cr + engine.m_fuel_cr + engine.m_residual_cr
    
    engine.fuel_film_cr = 0.0
    engine.fuel_film_cyl = 0.0


def apply_json_profile(engine, profile_key: str) -> bool:
    """
    Explicitly apply a JSON profile by key.
    Returns True if successful, False if profile not found.
    """
    json_profiles = load_json_profiles()
    if profile_key not in json_profiles:
        return False

    # Temporarily inject into ALL_PROFILES for apply_profile to find
    profile_data = json_profiles[profile_key]
    ALL_PROFILES[profile_key] = profile_data
    try:
        apply_profile(engine, profile_key)
        return True
    finally:
        # Clean up - remove the temporary entry
        if profile_key in ALL_PROFILES and profile_key not in [
            "am6_stock", "am6_stage6_rt_70", "am6_malossi_mhr_70", "am6_bigbore_80",
            "am6_longstroke_78", "am3_horizontal_stock", "am3_malossi_sport_70",
            "aerox_lc_stock", "aerox_lc_derestricted", "aerox_lc_malossi_mhr_70",
            "piaggio_c9_stock", "piaggio_c9_polini_70", "piaggio_c9_malossi_70",
            "derbi_ebe_stock", "derbi_ebe_polini_70", "derbi_d50b_stock"
        ]:
            del ALL_PROFILES[profile_key]


def list_profiles() -> list:
    """Returnera lista med alla tillgängliga legacy profilnycklar och namn."""
    return [(k, v["name"]) for k, v in ALL_PROFILES.items()]


def list_all_profiles() -> list:
    """
    Returnera lista med ALLA profilnycklar och namn (legacy + JSON v3.1).
    Format: [(key, name, source), ...] där source är 'legacy' eller 'json'.
    """
    result = [(k, v["name"], 'legacy') for k, v in ALL_PROFILES.items()]

    json_profiles = load_json_profiles()
    for key, data in json_profiles.items():
        if key not in ALL_PROFILES:
            result.append((key, data.get("name", key), 'json'))

    return sorted(result, key=lambda x: x[1])


if __name__ == "__main__":
    print("=" * 70)
    print("MOTORPROFILER - Legacy (Python) + JSON v3.1")
    print("=" * 70)

    # Show all profiles with source indication
    for key, name, source in list_all_profiles():
        # Get profile data based on source
        if source == 'legacy':
            p = ALL_PROFILES[key]
        else:
            json_profiles = load_json_profiles()
            p = json_profiles[key]

        bore_mm = p["B"] * 1000
        stroke_mm = p["stroke"] * 1000
        cc = math.pi * (bore_mm / 2) ** 2 * stroke_mm / 1000
        source_tag = "[legacy]" if source == 'legacy' else "[JSON]"
        print(f"  {key:<35} {name} {source_tag}")
        print(f"    {bore_mm:.1f}×{stroke_mm:.1f}mm = {cc:.1f}cc  "
              f"CR={p['compression_ratio']}:1  "
              f"{p['stock_power_kw']}kW @ {p['stock_rpm_peak']}RPM  "
              f"Exh={math.degrees(math.acos(1 - p['x_exh']*2/p['stroke']))*2:.0f}°")
        # Show metadata for JSON profiles
        if source == 'json':
            meta = get_json_profile_metadata(key)
            if meta['notes']:
                print(f"    Notes: {meta['notes'][:60]}...")
        print()
