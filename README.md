# Two-Stroke Engine Simulation

A high-fidelity thermodynamic and gas-dynamic simulation of a two-stroke engine, with both 2D (PyGame) and 3D (Godot 4.x) visualization.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Godot 4.6+](https://img.shields.io/badge/godot-4.6+-blue.svg)](https://godotengine.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

This project simulates a realistic two-stroke engine with accurate thermodynamics, gas dynamics, and combustion physics. It features:

- **Physics Engine**: 600 Hz thermodynamic simulation with real-time combustion, gas flows, and engine dynamics
- **2D Visualization**: PyGame-based interactive visualization with P-V diagrams, gauges, and particle effects
- **3D Visualization**: Godot 4.x Vulkan rendering with PBR materials, volumetric effects, and real-time animation
- **Tuning System**: Extensive parameter tuning with presets for different engine configurations

## Features

### Physics Simulation
- Real-time thermodynamic cycle (intake, compression, combustion, exhaust)
- Accurate slider-crank kinematics
- Pressure-wave tuned exhaust pipe simulation
- Reed valve dynamics with flutter
- Fuel film evaporation modeling
- Heat transfer and friction losses
- Scavenging efficiency calculations

### Visualization
- Real-time P-V diagrams (cylinder and crankcase)
- Animated piston, connecting rod, and crankshaft
- Pressure/flow visualizations
- Temperature heat maps
- Interactive tuning controls

### Engine Tuning
- **Stock**: Standard moped configuration
- **Gattrim**: Street-optimized reliability
- **Racing**: High-power competition setup
- **Classic**: 70s moped style
- **Dragrace**: Maximum acceleration setup
- **Custom**: Save/load your own configurations

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Windows 10/11 (primary platform)
- Vulkan-compatible GPU (for 3D mode)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/twostroke.git
cd twostroke

# Install dependencies
pip install -r requirements.txt
```

### Run 2D Mode (PyGame)

```bash
python main.py
```

### Run 3D Mode (Godot)

1. Download [Godot 4.6.2](https://godotengine.org/download) and place `Godot_v4.6.2-stable_win64.exe` in the `godot_engine/` directory
2. Launch with:

```bash
cd godot_engine
launch.bat
```

## Controls

### General
| Key | Action |
|-----|--------|
| `Space` | Pause/Resume |
| `P` | Toggle pause |
| `S` | Hold to engage starter motor |
| `I` | Toggle ignition on/off |
| `K` | Toggle fuel cutoff |

### Throttle & Fuel
| Key | Action |
|-----|--------|
| `↑` | Increase throttle |
| `↓` | Decrease throttle |
| `PgUp` | Increase fuel ratio |
| `PgDn` | Decrease fuel ratio |
| `Home` | Increase idle trim |
| `End` | Decrease idle trim |

### Timing & Tuning
| Key | Action |
|-----|--------|
| `←` | Retard ignition (decrease angle) |
| `→` | Advance ignition (increase angle) |
| `1-5` | Load tuning preset (Stock/Street/Racing/Classic/Dragrace) |
| `6/7` | Adjust compression ratio (+/-) |
| `8/9` | Adjust pipe resonance frequency (+/-) |
| `0` | Save current tuning to file |

### Quality Presets (2D Mode)
| Key | Preset |
|-----|--------|
| `F1` | Simple 2D |
| `F2` | Low |
| `F3` | Medium |
| `F4` | High |
| `F5` | Ultra |

### Additional Parameters
| Key | Action |
|-----|--------|
| `Shift + -` | Decrease stroke multiplier |
| `Shift + =` | Increase stroke multiplier |
| `[` / `]` | Decrease/Increase transfer port height |
| `;` / `'` | Decrease/Increase exhaust port height |
| `,` / `.` | Decrease/Increase reed stiffness |
| `/` / `\` | Decrease/Increase inertia multiplier |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Two-Stroke Engine                        │
│                     Simulation System                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌────────────┐  │
│  │   Physics    │←────→│   Engine     │←────→│   Tuning   │  │
│  │   Engine     │      │   Controller │      │   System   │  │
│  │  (600 Hz)    │      │              │      │            │  │
│  └──────────────┘      └──────────────┘      └────────────┘  │
│         ↓                                                     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Visualization Layer                   │  │
│  ├─────────────────┬─────────────────┬─────────────────────┤  │
│  │    2D PyGame    │   3D Godot 4.x  │    Data Export      │  │
│  │   (60 FPS)      │    (60 FPS)     │    (Real-time)      │  │
│  └─────────────────┴─────────────────┴─────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Project Structure

```
twostroke/
├── app.py                  # PyGame application entry
├── main.py                 # Simple main entry point
├── config.py               # Configuration and tuning presets
├── renderer.py             # 2D rendering system
├── particles.py            # Particle effects
├── engine_profiles.py      # Engine parameter profiles
├── validate_physics.py     # Physics validation suite
│
├── physics/                # Physics simulation package
│   ├── __init__.py
│   ├── engine_physics.py   # Main engine physics controller
│   ├── cylinder.py         # Cylinder thermodynamics
│   ├── combustion.py       # Combustion modeling
│   ├── thermodynamics.py   # Thermodynamic calculations
│   ├── kinematics.py       # Slider-crank kinematics
│   ├── flows.py            # Gas flow calculations
│   ├── friction.py         # Friction modeling
│   ├── constants.py        # Physical constants
│   └── utils.py            # Utility functions
│
├── rendering/              # Rendering utilities
│   ├── __init__.py
│   ├── animations.py       # Animation system
│   ├── bloom.py            # Bloom effects
│   ├── gauges.py           # Dashboard gauges
│   ├── materials.py        # Material definitions
│   └── procedural.py       # Procedural generation
│
├── tests/                  # Test suite
│   ├── test_physics.py     # Physics unit tests
│   ├── test_integration.py # Integration tests
│   ├── test_friction.py    # Friction tests
│   ├── test_scavenging.py  # Scavenging tests
│   └── test_units.py       # Unit tests
│
└── godot_engine/           # Godot 4.x 3D visualization
    ├── project.godot
    ├── launch.bat
    ├── scenes/
    ├── scripts/
    └── assets/
```

## Physics Model

### Thermodynamic Cycle

The simulation implements a complete two-stroke thermodynamic cycle:

1. **Intake/Scavenging**: Fresh charge enters through intake/reed valve, pushing exhaust out through transfer ports
2. **Compression**: Piston rises, compressing the fuel-air mixture
3. **Combustion**: Spark ignition initiates controlled burn with pressure rise
4. **Expansion**: Hot gases expand, pushing piston down (power stroke)
5. **Exhaust**: Exhaust port opens, pressure wave travels through tuned pipe

### Key Equations

**Slider-Crank Kinematics:**
```
x = R(1 - cos θ) + L(1 - √(1 - (R/L sin θ)²))
v = ωR(sin θ + (R/2L)sin 2θ / √(1 - (R/L sin θ)²))
```

**Cylinder Pressure:**
```
P = (m_air + m_fuel + m_burned) * R_specific * T_cyl / V_cyl
```

**Mass Flow (orifice equation):**
```
dm/dt = C_d * A * ρ_upstream * Φ(P_downstream/P_upstream)
```

See [API.md](API.md) for complete physics API documentation.

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=physics --cov-report=html

# Run specific test file
pytest tests/test_physics.py -v

# Run physics validation
python validate_physics.py
```

### Test Coverage

- **104 unit tests** covering physics calculations
- **53 validation tests** for engine behavior
- **Integration tests** for long-run stability
- **Division-by-zero guards** verified

## Performance

| Mode | Physics | Rendering | Target |
|------|---------|-----------|--------|
| 2D Simple | 600 Hz | 60 FPS | Any GPU |
| 2D Ultra | 600 Hz | 60 FPS | Mid-range GPU |
| 3D Godot | 600 Hz | 60 FPS | Vulkan GPU |

**Typical resource usage:**
- CPU: ~15% (single core) for physics
- Memory: ~200 MB (2D), ~400 MB (3D)
- GPU: Minimal (2D), Moderate (3D with effects)

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design
- **[API.md](API.md)** - Physics module API reference
- **[USER_GUIDE.md](USER_GUIDE.md)** - Detailed user manual
- **[DEVELOPER.md](DEVELOPER.md)** - Developer guide and contribution
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes

## Troubleshooting

### "Physics server connection failed" (Godot mode)
- Verify Python is installed: `python --version`
- Check that `physics_server.py` exists in `godot_engine/scripts/`
- Ensure port 9999 is not in use by another application

### "Godot crashes on startup"
- Update GPU drivers (Vulkan support required)
- Try running with `--rendering-driver opengl3` flag
- Check Windows Event Viewer for detailed error messages

### "Low FPS in 2D mode"
- Lower quality preset with `F1` or `F2`
- Disable bloom if enabled (major GPU impact)
- Reduce particle count in `config.py`

### "Engine won't start"
- Hold `S` to engage starter motor
- Ensure ignition is enabled (`I` to toggle)
- Check fuel isn't cut off (`K` to toggle)
- Verify fuel ratio is reasonable (0.03-0.08 typical)

## Contributing

See [DEVELOPER.md](DEVELOPER.md) for:
- Code style guidelines
- Testing requirements
- Architecture principles
- Pull request process

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- Physics model based on established two-stroke engine thermodynamics
- Godot integration inspired by real-time physics visualization techniques
- Tuning presets based on classic Swedish moped culture

## Contact

For questions, issues, or contributions, please use the GitHub issue tracker.
