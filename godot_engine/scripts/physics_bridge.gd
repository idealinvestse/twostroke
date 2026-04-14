class_name PhysicsBridge
extends Node

## Physics Bridge - Connects Godot to Python Physics Server
## Receives real-time engine state via TCP socket with length-prefix protocol

signal state_received(state: Dictionary)
signal connected
signal disconnected

@export var host: String = "127.0.0.1"
@export var port: int = 9999
@export var reconnect_delay: float = 2.0

var socket: StreamPeerTCP = null
var is_connected: bool = false
var physics_state: Dictionary = {}
var _running: bool = true
var _recv_buffer: PackedByteArray = PackedByteArray()

func _ready():
	# Start polling timer instead of thread (Godot 4.x best practice)
	var timer = Timer.new()
	timer.wait_time = 0.016  # ~60Hz
	timer.autostart = true
	timer.one_shot = false
	timer.timeout.connect(_poll_connection)
	add_child(timer)
	_connect_to_server()
	
	# Connect to GameStateManager signals for pause/restart control
	if GameStateManager:
		GameStateManager.pause_requested.connect(_on_pause_requested)
		GameStateManager.restart_requested.connect(_on_restart_requested)

func _exit_tree():
	_running = false
	if socket:
		socket.disconnect_from_host()
		socket = null

func _connect_to_server():
	"""Attempt to connect to Python physics server."""
	if socket:
		socket.disconnect_from_host()
		socket = null
		_recv_buffer.clear()
	
	socket = StreamPeerTCP.new()
	var err = socket.connect_to_host(host, port)
	
	if err == OK:
		print("Connecting to physics server...")
	else:
		socket = null
		print("Failed to initiate connection: ", err)

func _poll_connection():
	"""Poll TCP connection and process data (called from main thread)."""
	if not _running:
		return
	
	if not socket:
		_connect_to_server()
		return
	
	# Update socket status
	socket.poll()
	var status = socket.get_status()
	
	match status:
		StreamPeerTCP.STATUS_CONNECTING:
			# Still connecting, wait
			return
		StreamPeerTCP.STATUS_CONNECTED:
			if not is_connected:
				is_connected = true
				emit_signal("connected")
				print("Connected to physics server")
			_receive_data()
		StreamPeerTCP.STATUS_ERROR:
			if is_connected:
				is_connected = false
				emit_signal("disconnected")
				print("Connection error")
			socket.disconnect_from_host()
			socket = null
			# Schedule reconnect
			get_tree().create_timer(reconnect_delay).timeout.connect(_connect_to_server)
		StreamPeerTCP.STATUS_NONE:
			if is_connected:
				is_connected = false
				emit_signal("disconnected")
				print("Disconnected from physics server")
			socket = null
			# Schedule reconnect
			get_tree().create_timer(reconnect_delay).timeout.connect(_connect_to_server)

func _receive_data():
	"""Receive and parse length-prefixed JSON from physics server."""
	if not socket:
		return
	
	var available = socket.get_available_bytes()
	if available <= 0:
		return
	
	# Read available data into buffer
	var data = socket.get_data(available)
	if data[0] != OK:
		return
	
	_recv_buffer.append_array(data[1] as PackedByteArray)
	
	# Process complete messages (4-byte length prefix + JSON payload)
	while _recv_buffer.size() >= 4:
		# Read message length (big-endian uint32)
		var msg_len = _recv_buffer[0] << 24 | _recv_buffer[1] << 16 | _recv_buffer[2] << 8 | _recv_buffer[3]
		
		if msg_len <= 0 or msg_len > 65536:  # Sanity check (max 64KB)
			_recv_buffer = _recv_buffer.slice(1)  # Skip bad byte and resync
			continue
		
		if _recv_buffer.size() < 4 + msg_len:
			break  # Incomplete message, wait for more data
		
		# Extract message payload
		var payload = _recv_buffer.slice(4, 4 + msg_len)
		_recv_buffer = _recv_buffer.slice(4 + msg_len)
		
		# Parse JSON
		var json_str = payload.get_string_from_utf8()
		var json = JSON.new()
		var err = json.parse(json_str)
		
		if err == OK:
			physics_state = json.data
			emit_signal("state_received", physics_state)
		else:
			print("JSON parse error: ", json.get_error_message())

func get_physics_state() -> Dictionary:
	"""Get current physics state (main thread only)."""
	return physics_state.duplicate()

func send_command(command: String, value):
	"""Send control command to physics server."""
	if not is_connected or not socket:
		return
	
	var cmd = "%s:%s\n" % [command, str(value)]
	socket.put_data(cmd.to_utf8_buffer())

# Convenience methods for engine controls
func set_throttle(value: float):
	send_command("THROTTLE", clampf(value, 0.0, 1.0))

func set_ignition_angle(angle: float):
	send_command("IGNITION", angle)

func set_starter(active: bool):
	send_command("STARTER", active)

func set_ignition_enabled(enabled: bool):
	send_command("IGNITION_ON", enabled)

func set_fuel_cutoff(cutoff: bool):
	send_command("FUEL_CUTOFF", cutoff)

func set_fuel_ratio(ratio: float):
	send_command("FUEL_RATIO", ratio)

func set_idle_trim(trim: float):
	send_command("IDLE_TRIM", trim)

func set_pause_state(paused: bool):
	"""Send pause command to physics server."""
	send_command("PAUSE", paused)

func restart_simulation():
	"""Send restart command to physics server."""
	send_command("RESTART", "1")

func select_profile(profile_key: String):
	"""Send profile selection command to physics server."""
	send_command("PROFILE", profile_key)

func _on_pause_requested(paused: bool):
	"""Handle pause request from GameStateManager."""
	set_pause_state(paused)

func _on_restart_requested():
	"""Handle restart request from GameStateManager."""
	restart_simulation()
