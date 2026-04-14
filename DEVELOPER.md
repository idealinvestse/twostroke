# Developer Guide

This guide is for developers who want to contribute to or modify the Two-Stroke Engine Simulation.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Architecture Principles](#architecture-principles)
- [Testing](#testing)
- [Adding Features](#adding-features)
- [Debugging](#debugging)
- [Performance](#performance)
- [Release Process](#release-process)

## Development Setup

### Prerequisites

```bash
# Python 3.11 or higher
python --version

# Git
git --version

# (Optional) Godot 4.6+ for 3D development
```

### Install Dependencies

```bash
# Clone repository
git clone https://github.com/yourusername/twostroke.git
cd twostroke

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov ruff mypy
```

### Verify Setup

```bash
# Run tests
pytest tests/ -v

# Run physics validation
python validate_physics.py

# Run 2D mode
python main.py

# Run linter
ruff check .
```

## Code Style

We use automated tools to enforce code quality:

### Ruff (Linting & Formatting)

```bash
# Check all files
ruff check .

# Auto-fix issues
ruff check . --fix

# Check specific file
ruff check physics/engine_physics.py
```

### Configuration

Ruff configuration is in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E402"]  # Module level import not at top (intentional in physics_server.py)
```

### Code Style Rules

1. **Line Length**: 120 characters maximum
2. **Imports**: Grouped by stdlib, third-party, local
3. **Type Hints**: Required for all public functions
4. **Docstrings**: Google-style for public APIs
5. **Naming**:
   - Classes: `PascalCase`
   - Functions/variables: `snake_case`
   - Constants: `UPPER_SNAKE_CASE`
   - Private: `_leading_underscore`

### Example

```python
"""Physics module for engine simulation."""

from dataclasses import dataclass
from typing import Tuple

import numpy as np  # third-party

from physics.constants import T_ATM  # local


@dataclass
class EngineState:
    """Immutable engine state snapshot.
    
    Attributes:
        theta: Crank angle in radians.
        omega: Angular velocity in rad/s.
    """
    theta: float
    omega: float


def calculate_kinematics(
    theta: float,
    R: float,
    L: float
) -> Tuple[float, float]:
    """Calculate piston position and velocity.
    
    Args:
        theta: Crank angle in radians.
        R: Crank radius in meters.
        L: Connecting rod length in meters.
        
    Returns:
        Tuple of (position, velocity) in meters and m/s.
        
    Raises:
        ValueError: If R or L is not positive.
    """
    if R <= 0 or L <= 0:
        raise ValueError("R and L must be positive")
    
    position = R * (1 - np.cos(theta)) + L * (1 - np.sqrt(1 - (R/L * np.sin(theta))**2))
    velocity = R * np.sin(theta)  # Simplified
    
    return position, velocity
```

## Architecture Principles

### 1. Separation of Concerns

Physics engine must not depend on visualization:

```python
# CORRECT: Physics knows nothing about rendering
class EnginePhysics:
    def step(self, dt: float) -> EngineSnapshot:
        # Pure physics calculations
        return EngineSnapshot(...)

# INCORRECT: Physics depending on rendering
class EnginePhysics:
    def step(self, dt: float, renderer: Renderer) -> None:  # ❌ Don't do this
        renderer.draw_something()  # ❌ Don't do this
```

### 2. Fixed Timestep

Physics must use fixed timestep for stability:

```python
PHYSICS_DT = 1.0 / 600.0  # Fixed at 600 Hz

# In application loop
accumulator += raw_dt
while accumulator >= PHYSICS_DT:
    state = engine.step(PHYSICS_DT)
    accumulator -= PHYSICS_DT
```

### 3. Immutable State

State snapshots must be immutable:

```python
@dataclass(frozen=True)  # frozen=True makes it immutable
class EngineSnapshot:
    theta: float
    # ...

# Can be safely shared, cached, or used in multiple places
snapshot = engine.step(dt)
renderer.draw(snapshot)
logger.log(snapshot)
```

### 4. Defensive Programming

Guard all divisions and validate state:

```python
# Always guard divisions
denominator = max(some_value, 1e-9)
result = numerator / denominator

# Validate state periodically
engine.validate_state()  # Raises on invalid state
```

### 5. Modularity

Each physics subsystem should be independently testable:

```python
# kinematics.py - No dependencies on other physics modules
class SliderCrankKinematics:
    def calculate(self, theta: float) -> KinematicState:
        # Pure geometry, no physics
        ...

# Can test independently
import pytest

def test_kinematics_at_tdc():
    k = SliderCrankKinematics(R=0.02, L=0.095)
    state = k.calculate(theta=0)
    assert state.x == 0  # At TDC
```

## Testing

### Test Organization

```
tests/
├── test_physics.py        # Core physics calculations
├── test_integration.py    # Multi-step scenarios
├── test_friction.py       # Friction model specifically
├── test_scavenging.py     # Scavenging models
└── test_units.py          # Unit tests for utilities
```

### Writing Tests

```python
import pytest
from physics import EnginePhysics, T_ATM


def test_engine_initial_state():
    """Test that engine starts with correct initial conditions."""
    engine = EnginePhysics()
    
    assert engine.theta == pytest.approx(0.314, abs=0.01)  # ~18 degrees
    assert engine.omega == 0.0  # Starts at rest
    
    state = engine.snapshot()
    assert state.T_cyl == pytest.approx(T_ATM)
    assert state.p_cyl > 0


def test_division_by_zero_guarded():
    """Test that division by zero is guarded."""
    engine = EnginePhysics()
    
    # Set up extreme conditions that might cause division by zero
    engine.m_air_cyl = 0.0
    engine.m_fuel_cyl = 0.0
    
    # Should not raise
    state = engine.step(1.0 / 600.0)
    
    # State should still be valid
    assert state.p_cyl > 0  # Minimum pressure guard applied


@pytest.mark.parametrize("throttle", [0.0, 0.5, 1.0])
def test_throttle_range(throttle):
    """Test engine behavior across throttle range."""
    engine = EnginePhysics()
    engine.throttle = throttle
    
    # Run for 1 second
    for _ in range(600):
        state = engine.step(1.0 / 600.0)
    
    # Engine should be running
    assert state.omega >= 0
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_physics.py

# Run specific test
pytest tests/test_physics.py::test_engine_initial_state

# Run with coverage
pytest --cov=physics --cov-report=html

# Run validation suite
python validate_physics.py

# Run benchmarks
pytest tests/ --benchmark-only
```

### Test Coverage Requirements

- Minimum 80% coverage for physics module
- All public methods must have tests
- Edge cases (zero, infinity, NaN) must be tested
- Integration tests for 10+ second runs

## Adding Features

### Adding a New Physics Feature

1. **Identify the module**: Which physics subsystem?
   - Kinematics → `physics/kinematics.py`
   - Thermodynamics → `physics/thermodynamics.py`
   - Flows → `physics/flows.py`
   - etc.

2. **Implement the feature**:

```python
# physics/flows.py

def calculate_new_flow(
    P1: float,
    P2: float,
    area: float,
    temperature: float
) -> float:
    """Calculate new type of flow.
    
    Args:
        P1: Upstream pressure (Pa)
        P2: Downstream pressure (Pa)
        area: Flow area (m²)
        temperature: Gas temperature (K)
        
    Returns:
        Mass flow rate in kg/s.
    """
    # Implementation
    # ...
    
    # Guard division
    denominator = max(some_calculation, 1e-9)
    
    return result
```

3. **Add tests**:

```python
# tests/test_physics.py

def test_new_flow_basic():
    """Test new flow calculation."""
    result = calculate_new_flow(
        P1=200000.0,
        P2=100000.0,
        area=0.001,
        temperature=300.0
    )
    
    assert result > 0
    assert result < 1.0  # Sanity check


def test_new_flow_zero_pressure():
    """Test with zero pressure differential."""
    result = calculate_new_flow(
        P1=100000.0,
        P2=100000.0,
        area=0.001,
        temperature=300.0
    )
    
    assert result == 0.0  # No flow without pressure difference
```

4. **Integrate into EnginePhysics**:

```python
# physics/engine_physics.py

class EnginePhysics:
    def step(self, dt: float, starter_motor: bool = False) -> EngineSnapshot:
        # ... existing code ...
        
        # Add new flow calculation
        new_flow = self._calculate_new_flow(...)
        
        # Update masses
        # ...
```

5. **Update documentation**:
   - Add to `API.md`
   - Update `ARCHITECTURE.md` if architecture changes
   - Add example to docstring

### Adding a New Tuning Parameter

1. **Add to config.py**:

```python
# config.py

TUNING_PRESETS = {
    TuningPreset.STOCK: {
        # ... existing params ...
        "new_parameter": 1.0,
    }
}
```

2. **Add to EnginePhysics**:

```python
# physics/engine_physics.py

class EnginePhysics:
    def __init__(self):
        # ...
        self.new_parameter: float = 1.0
```

3. **Apply preset**:

```python
# config.py

def apply_tuning_preset(engine, preset: TuningPreset) -> None:
    settings = get_tuning_preset(preset)
    engine.new_parameter = settings["new_parameter"]
```

4. **Add keyboard control** (if interactive):

```python
# app.py

elif event.key == pygame.K_n:
    self.engine.new_parameter = min(2.0, self.engine.new_parameter + 0.1)
    print(f"New param: {self.engine.new_parameter:.1f}")
```

5. **Save/load support**:

```python
# config.py

def save_tuning_preset(engine, name: str, filepath: str = None) -> str:
    settings = {
        # ... existing ...
        "new_parameter": engine.new_parameter,
    }
    # ...

def load_tuning_preset(engine, filepath: str) -> bool:
    engine.new_parameter = settings.get("new_parameter", 1.0)
```

## Debugging

### Enabling Debug Output

```python
# In your test or script
import logging
logging.basicConfig(level=logging.DEBUG)

# In physics modules
import logging
logger = logging.getLogger(__name__)

logger.debug(f"Theta: {self.theta:.3f}, P_cyl: {self.p_cyl:.0f}")
```

### State Inspection

```python
# Print detailed state
state = engine.step(dt)

# Use dataclass __repr__
print(state)

# Access specific fields
print(f"Cylinder pressure: {state.p_cyl / 1000:.1f} kPa")
print(f"Temperature: {state.T_cyl - 273.15:.1f} °C")
print(f"Lambda: {state.lambda_value:.2f}")
```

### Visual Debugging

```python
# In app.py, add to draw method

# Draw debug overlay
def draw_debug_info(self, screen, state):
    debug_text = f"""
    FPS: {self.clock.get_fps():.1f}
    Theta: {state.theta:.3f} rad ({math.degrees(state.theta):.1f}°)
    P_cyl: {state.p_cyl/1000:.1f} kPa
    Mass: {state.m_air_cyl + state.m_fuel_cyl:.6f} kg
    """
    # Render text...
```

### Common Issues

#### "Division by zero" warnings

Add guards:

```python
denominator = max(some_value, 1e-9)
result = numerator / denominator
```

#### NaN in state

Enable validation:

```python
# In physics/engine_physics.py

def step(self, dt: float) -> EngineSnapshot:
    # ... calculations ...
    
    # Validate before returning
    self.validate_state()
    
    return self.snapshot()
```

#### Engine won't start

Check:
- Is ignition enabled? (`engine.ignition_enabled`)
- Is fuel present? (`engine.m_fuel_cyl > 1e-6`)
- Is starter motor engaged?
- Are port timings correct?

## Performance

### Profiling

```bash
# Profile physics step
python -m cProfile -o profile.stats -c "
from physics import EnginePhysics
engine = EnginePhysics()
for _ in range(6000):
    engine.step(1.0/600.0)
"

# Analyze results
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)
"
```

### Optimization Tips

1. **Avoid allocations in hot path**:

```python
# BAD: Allocates every step
def step(self, dt: float) -> EngineSnapshot:
    new_list = []  # ❌ Allocation
    return EngineSnapshot(...)  # ❌ Allocation

# GOOD: Reuse objects where possible
# (But frozen dataclasses are immutable, so this is tricky)
# Profile first, optimize only if needed
```

2. **Pre-calculate constants**:

```python
# In __init__
self._precomputed_value = self._expensive_calculation()

# In step, use cached value
result = self._precomputed_value * something
```

3. **Use numpy for vector operations**:

```python
# For operations on many particles or data points
import numpy as np

positions = np.array([...])
velocities = np.array([...])

# Vectorized operation
new_positions = positions + velocities * dt
```

### Memory Management

```python
# Limit collections
deque(maxlen=300)  # Automatically drops old entries

# Clear particles when too many
if len(particles) > MAX_PARTICLES:
    particles = particles[-MAX_PARTICLES:]
```

## Release Process

1. **Update version**: In `__init__.py` or `config.py`

2. **Update CHANGELOG.md**: Document all changes

3. **Run full test suite**:

```bash
pytest tests/ -v --cov=physics --cov-report=html
python validate_physics.py
```

4. **Check code quality**:

```bash
ruff check .
mypy physics/ --ignore-missing-imports
```

5. **Update documentation**: Ensure all changes are documented

6. **Create git tag**:

```bash
git tag -a v3.0.0 -m "Version 3.0.0 - Godot migration"
git push origin v3.0.0
```

## Resources

- [PyGame Documentation](https://www.pygame.org/docs/)
- [Godot Documentation](https://docs.godotengine.org/)
- [Two-Stroke Engine Theory](https://www.amazon.com/Two-Stroke-Engine-Technology-Gordon-Blair/dp/0768004409)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## Getting Help

- Open an issue on GitHub for bugs
- Start a discussion for questions
- Check existing tests for usage examples
- Read the architecture documentation
