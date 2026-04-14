# Bug Fixes & Improvements - v3.0 Godot Migration

## Date: 2026-04-11

### Critical Fixes (Would Crash)

1. **physics_server.py - Removed PyGame Dependencies**
   - **Problem:** Imported `spawn_particles` and `update_particles` which depend on PyGame (`RENDER.scale`, `RENDER.crank_x`)
   - **Fix:** Removed particle system entirely from physics server. Particles are handled by Godot's GPU particle system.
   - **Files:** `godot_engine/scripts/physics_server.py`

2. **physics_server.py - Fixed Missing Attribute**
   - **Problem:** `self.engine.frame_count` doesn't exist on `EnginePhysics`
   - **Fix:** Added `_tick_count` counter to track physics ticks
   - **Files:** `godot_engine/scripts/physics_server.py`

3. **physics_server.py - Fixed PyGame Pixel Calculations**
   - **Problem:** `cylinder_y = 550 - (self.engine.R + self.engine.L) * 3000.0` is PyGame-specific pixel math
   - **Fix:** Removed all PyGame-specific calculations
   - **Files:** `godot_engine/scripts/physics_server.py`

4. **physics_bridge.gd - Fixed Godot 4.x API**
   - **Problem:** `socket.set_blocking_mode(false)` doesn't exist in Godot 4.x `StreamPeerTCP`
   - **Fix:** Used `socket.poll()` with timer-based polling (Godot 4.x best practice)
   - **Files:** `godot_engine/scripts/physics_bridge.gd`

### Medium Priority Fixes

5. **physics_server.py - Fixed JSON Protocol**
   - **Problem:** No length prefix on JSON messages, causing split/broken reads
   - **Fix:** Added 4-byte big-endian length prefix protocol
   - **Files:** `godot_engine/scripts/physics_server.py`, `godot_engine/scripts/physics_bridge.gd`

6. **physics_server.py - Made Path Relative**
   - **Problem:** Hard-coded path `d:\\PyGame\\twostroke`
   - **Fix:** Uses `os.path.abspath` with relative path from script location
   - **Files:** `godot_engine/scripts/physics_server.py`

7. **renderer.py - Fixed Dashboard Overlap**
   - **Problem:** Dashboard at (900, 650) overlapped with PV diagrams at x=900
   - **Fix:** Moved dashboard to y=660 (PV diagrams end at y=630)
   - **Files:** `renderer.py`

8. **renderer.py - Fixed Hardcoded dt**
   - **Problem:** `dt=1.0` hardcoded in animation update
   - **Fix:** Added `dt` parameter to `draw()` method, passed from `app.py`
   - **Files:** `renderer.py`, `app.py`

9. **config.py - Fixed Bloom Default Confusion**
   - **Problem:** `enable_bloom: bool = True` but MEDIUM preset disables it
   - **Fix:** Changed default to `False` with comment explaining it requires HIGH/ULTRA
   - **Files:** `config.py`

10. **launch.bat - Fixed Process Killing**
    - **Problem:** `taskkill /F /IM "%GODOT_PATH%"` doesn't work with path variable
    - **Fix:** Use `taskkill /FI "WINDOWTITLE eq ..."` to kill by window title
    - **Files:** `godot_engine/launch.bat`

11. **engine_controller.gd - Added Error Handling**
    - **Problem:** No null checks for optional node references
    - **Fix:** Added `get_node_or_null()` and type checking for all references
    - **Files:** `godot_engine/scripts/engine_controller.gd`

12. **engine_controller.gd - Fixed Scale Factor**
    - **Problem:** `scale_3d: float = 10.0` too small for 3D models
    - **Fix:** Changed to `20.0` to match actual 3D model dimensions
    - **Files:** `godot_engine/scripts/engine_controller.gd`

### Improvements

13. **physics_server.py - Added Buffer Handling**
    - Added `_recv_buffer` to handle partial TCP reads
    - Added `_process_buffer()` to extract complete commands
    - Files: `godot_engine/scripts/physics_server.py`

14. **physics_server.py - Added More Physics Data**
    - Added `omega`, `a_exh`, `a_tr`, `a_in`, `dm_exh`, `dm_tr`, `dm_air_in`, `dm_fuel_in` to state
    - Files: `godot_engine/scripts/physics_server.py`

15. **physics_bridge.gd - Added Reconnection Logic**
    - Added automatic reconnection with delay
    - Files: `godot_engine/scripts/physics_bridge.gd`

16. **physics_server.py - Added New Commands**
    - Added `FUEL_RATIO` and `IDLE_TRIM` commands
    - Files: `godot_engine/scripts/physics_server.py`, `godot_engine/scripts/physics_bridge.gd`

## Summary

- **Critical fixes:** 4 (would crash immediately)
- **Medium fixes:** 8 (would cause bugs or poor UX)
- **Improvements:** 4 (enhanced functionality)

All files now:
- ✅ Have correct imports and API usage
- ✅ Handle missing data gracefully
- ✅ Use relative paths
- ✅ Have proper error handling
- ✅ Follow platform-specific best practices
