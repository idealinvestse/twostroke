"""Physics Server for Godot Engine v3.0

Provides real-time engine physics data to Godot via TCP socket.
Runs the existing 2-stroke engine simulation and streams state.
Particles are handled by Godot's GPU particle system - not here.
"""

import sys
import os
import json
import socket
import struct
import time
from collections import deque

# Add parent directory to path to import physics modules (relative path)
_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _parent_dir)

from physics import EnginePhysics

# Server configuration
HOST = '127.0.0.1'
PORT = 9999
PHYSICS_HZ = 600
DT = 1.0 / PHYSICS_HZ
SEND_HZ = 60
SEND_INTERVAL = PHYSICS_HZ // SEND_HZ  # Every 10th frame


class PhysicsServer:
    """TCP server that streams engine physics state to Godot."""
    
    def __init__(self):
        self.engine = EnginePhysics()
        self.pv_cyl_points: deque = deque(maxlen=300)
        self.pv_cr_points: deque = deque(maxlen=300)
        self.running = True
        self._starter_pressed = False
        self._tick_count = 0
        
        # Create TCP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((HOST, PORT))
        self.socket.listen(1)
        
    def handle_client(self, conn):
        """Handle connection from Godot client."""
        print("Godot client connected")
        conn.setblocking(False)
        self._recv_buffer = b''
        conn.settimeout(1.0)  # Add timeout for recv operations
        
        next_update = time.time()
        last_send_time = time.time()
        send_interval = 1.0 / SEND_HZ
        
        while self.running:
            # Check for commands from Godot
            try:
                data = conn.recv(4096)
                if data:
                    self._recv_buffer += data
                    self._process_buffer()
                elif data == b'':
                    # Connection closed by client
                    print("Client disconnected (empty recv)")
                    break
            except BlockingIOError:
                pass
            except socket.timeout:
                pass
            except ConnectionResetError:
                print("Client disconnected (reset)")
                break
            except ConnectionAbortedError:
                print("Client disconnected (aborted)")
                break
            except Exception as e:
                print(f"Connection error: {e}")
                break
            
            # Physics update at 600 Hz
            current_time = time.time()
            if current_time >= next_update:
                try:
                    state = self.step_physics()
                    self._tick_count += 1
                    
                    # Send state to Godot at 60 Hz (time-based to be more robust)
                    if current_time - last_send_time >= send_interval:
                        self.send_state(conn, state)
                        last_send_time = current_time
                    
                    next_update = current_time + DT
                except Exception as e:
                    print(f"Physics step error: {e}")
                    # Continue running even if physics step fails
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.0005)
    
    def _process_buffer(self):
        """Process buffered data for complete commands."""
        while b'\n' in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split(b'\n', 1)
            if line.strip():
                self.process_command(line.decode('utf-8', errors='ignore'))
    
    def process_command(self, data: str):
        """Process control commands from Godot."""
        try:
            commands = data.strip().split('\n')
            for cmd in commands:
                if not cmd:
                    continue
                    
                parts = cmd.split(':', 1)  # Split on first colon only
                if len(parts) != 2:
                    continue
                    
                key, value = parts[0].strip(), parts[1].strip()
                
                if key == 'THROTTLE':
                    val = float(value)
                    if 0.0 <= val <= 1.0:
                        self.engine.throttle = val
                elif key == 'IGNITION':
                    val = float(value)
                    if 270.0 <= val <= 450.0:  # Valid ignition angle range
                        self.engine.ignition_angle_deg = val
                elif key == 'STARTER':
                    self._starter_pressed = value.upper() in ('TRUE', '1', 'YES')
                elif key == 'IGNITION_ON':
                    self.engine.ignition_enabled = value.upper() in ('TRUE', '1', 'YES')
                elif key == 'FUEL_CUTOFF':
                    self.engine.fuel_cutoff = value.upper() in ('TRUE', '1', 'YES')
                elif key == 'FUEL_RATIO':
                    val = float(value)
                    if 10.0 <= val <= 20.0:  # Valid lambda range
                        self.engine.fuel_ratio = val
                elif key == 'IDLE_TRIM':
                    val = float(value)
                    if -0.5 <= val <= 0.5:
                        self.engine.idle_fuel_trim = val
                    
        except (ValueError, AttributeError) as e:
            print(f"Command error: {e}")
    
    def step_physics(self):
        """Run one physics step."""
        state = self.engine.step(DT, self._starter_pressed)
        
        # Collect PV data
        v_cyl_cc = (self.engine.V_c + self.engine.A_p * state.x) * 1e6
        v_cr_cc = (self.engine.V_cr_min + self.engine.A_p * (2 * self.engine.R - state.x)) * 1e6
        self.pv_cyl_points.append((v_cyl_cc, state.p_cyl / 100000.0))
        self.pv_cr_points.append((v_cr_cc, state.p_cr / 100000.0))
        
        return state
    
    def send_state(self, conn, state):
        """Send engine state to Godot as length-prefixed JSON."""
        try:
            # Build cylinder data list for multi-cylinder support
            cylinders_data = []
            if hasattr(state, 'cylinders') and state.cylinders:
                for cyl in state.cylinders:
                    cylinders_data.append({
                        'p_cyl': float(cyl.p_cyl),
                        'T_cyl': float(cyl.T_cyl),
                        'm_air': float(cyl.m_air),
                        'm_fuel': float(cyl.m_fuel),
                        'burn_fraction': float(cyl.burn_fraction),
                        'combustion_active': bool(cyl.combustion_active),
                        'spark_active': bool(cyl.spark_active),
                    })
            
            # Validate state data before sending
            data = {
                'theta': float(self.engine.theta) if hasattr(self.engine, 'theta') else 0.0,
                'omega': float(self.engine.omega) if hasattr(self.engine, 'omega') else 0.0,
                'rpm': float(state.rpm) if hasattr(state, 'rpm') else 0.0,
                'x': float(state.x) if hasattr(state, 'x') else 0.0,
                'p_cyl': float(state.p_cyl) if hasattr(state, 'p_cyl') else 0.0,
                'p_cr': float(state.p_cr) if hasattr(state, 'p_cr') else 0.0,
                'p_exh_pipe': float(state.p_exh_pipe) if hasattr(state, 'p_exh_pipe') else 0.0,
                'T_cyl': float(state.T_cyl) if hasattr(state, 'T_cyl') else 293.0,
                'T_cr': float(self.engine.T_cr) if hasattr(self.engine, 'T_cr') else 293.0,
                'burn_fraction': float(state.burn_fraction) if hasattr(state, 'burn_fraction') else 0.0,
                'combustion_active': bool(state.combustion_active) if hasattr(state, 'combustion_active') else False,
                'spark_active': bool(state.spark_active) if hasattr(state, 'spark_active') else False,
                'reed_opening': float(self.engine.reed_opening) if hasattr(self.engine, 'reed_opening') else 0.0,
                'throttle': float(self.engine.throttle) if hasattr(self.engine, 'throttle') else 0.0,
                'lambda': float(self.engine.lambda_value) if hasattr(self.engine, 'lambda_value') else 14.7,
                'power_kw': float(state.power_kw) if hasattr(state, 'power_kw') else 0.0,
                'torque': float(state.torque) if hasattr(state, 'torque') else 0.0,
                've': float(state.volumetric_efficiency) if hasattr(state, 'volumetric_efficiency') else 0.0,
                'te': float(state.trapping_efficiency) if hasattr(state, 'trapping_efficiency') else 0.0,
                'a_exh': float(state.a_exh) if hasattr(state, 'a_exh') else 0.0,
                'a_tr': float(state.a_tr) if hasattr(state, 'a_tr') else 0.0,
                'a_in': float(state.a_in) if hasattr(state, 'a_in') else 0.0,
                'num_cylinders': len(cylinders_data),
                'cylinders': cylinders_data,
                'pv_cyl': list(self.pv_cyl_points)[-60:] if self.pv_cyl_points else [],
                'pv_cr': list(self.pv_cr_points)[-60:] if self.pv_cr_points else [],
            }
            
            json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
            # Length-prefix protocol: 4 bytes length + JSON payload
            length_prefix = struct.pack('!I', len(json_bytes))
            conn.send(length_prefix + json_bytes)
            
        except (BlockingIOError, ConnectionResetError, ConnectionAbortedError):
            pass
        except OSError:
            pass
        except Exception as e:
            print(f"Send error: {e}")
    
    def run(self):
        """Main server loop."""
        print(f"Physics server starting on {HOST}:{PORT}")
        print(f"Physics: {PHYSICS_HZ} Hz, Send: {SEND_HZ} Hz")
        print("Waiting for Godot connection...")
        
        while self.running:
            try:
                conn, addr = self.socket.accept()
                print(f"Connection from {addr}")
                self.handle_client(conn)
                conn.close()
            except KeyboardInterrupt:
                print("\nShutting down...")
                self.running = False
            except Exception as e:
                print(f"Server error: {e}")
                time.sleep(1)
        
        self.socket.close()


if __name__ == '__main__':
    server = PhysicsServer()
    server.run()
