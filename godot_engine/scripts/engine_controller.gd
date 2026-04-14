class_name EngineController
extends Node3D

## Main Engine Controller - Coordinates physics, animation, and UI
## Manages 3D engine visualization with real-time thermodynamics

@export var physics_bridge: NodePath
@export var crankshaft: NodePath
@export var conrod: NodePath
@export var piston: NodePath
@export var reed_valve: NodePath
@export var spark_plug: NodePath
@export var cylinder_head: NodePath

# Engine geometry (matching Python physics from physics/constants.py)
var R: float = 0.03  # Crank radius (30mm)
var L: float = 0.06  # Conrod length (60mm)
var B: float = 0.044 # Bore (44mm)
var scale_3d: float = 10.0  # Visual scale factor (stroke 0.04m*10 = 0.4 units, fits 0.8-unit cylinder)

# Component references
var _physics: Node = null
var _crankshaft: Node3D = null
var _conrod: Node3D = null
var _piston: Node3D = null
var _reed: Node3D = null
var _spark: Node3D = null
var _head: Node3D = null

# State tracking
var current_theta: float = 0.0
var current_rpm: float = 0.0
var is_combusting: bool = false
var spark_active: bool = false

# Visual effects
@export var combustion_glow: NodePath
@export var exhaust_particles: NodePath
@export var gas_flow_particles: NodePath

func _ready():
	# Get component references with error handling
	if physics_bridge:
		var node = get_node_or_null(physics_bridge)
		if node:
			_physics = node
			if _physics.has_signal("state_received"):
				_physics.connect("state_received", Callable(self, "_on_physics_state"))
			if _physics.has_signal("connected"):
				_physics.connect("connected", Callable(self, "_on_connected"))
			if _physics.has_signal("disconnected"):
				_physics.connect("disconnected", Callable(self, "_on_disconnected"))
		else:
			print("Warning: physics_bridge node not found")
	
	if crankshaft:
		_crankshaft = get_node_or_null(crankshaft) as Node3D
	if conrod:
		_conrod = get_node_or_null(conrod) as Node3D
	if piston:
		_piston = get_node_or_null(piston) as Node3D
	if reed_valve:
		_reed = get_node_or_null(reed_valve) as Node3D
	if spark_plug:
		_spark = get_node_or_null(spark_plug) as Node3D
	if cylinder_head:
		_head = get_node_or_null(cylinder_head) as Node3D
	
	print("Engine controller initialized")

func _on_physics_state(state: Dictionary):
	"""Handle new physics state from server."""
	# Update tracking variables with safe access
	current_theta = state.get("theta", 0.0)
	current_rpm = state.get("rpm", 0.0)
	is_combusting = state.get("combustion_active", false)
	spark_active = state.get("spark_active", false)
	
	# Update animations
	_update_slider_crank(state)
	_update_effects(state)
	_update_reed_valve(state)
	_update_spark(state)

func _update_slider_crank(state: Dictionary):
	"""Update slider-crank mechanism animation."""
	var theta = state.get("theta", 0.0)
	var x = state.get("x", 0.0)  # Piston position from TDC
	
	# Crankshaft rotation
	if _crankshaft:
		_crankshaft.rotation.z = theta
	
	# Piston position: x=0 at TDC (near head), increases downward
	if _piston:
		# 0.65 = TDC world-y (top of cylinder barrel); subtract to move piston down as x grows
		var piston_y = 0.65 - x * scale_3d
		_piston.position.y = piston_y
	
	# Conrod angle and position
	if _conrod and _crankshaft and _piston:
		var crank_pin = _get_crank_pin_position(theta)
		# Wrist pin is offset from piston body (based on piston.tscn transform: y=-0.05 Godot units)
		var wrist_pin_offset_y = -0.05
		var wrist_pin = _piston.position + Vector3(0, wrist_pin_offset_y, 0)
		
		# Calculate conrod angle (between crank pin and wrist pin)
		var delta = wrist_pin - crank_pin
		var angle = atan2(delta.x, delta.y)
		_conrod.rotation.z = angle
		
		# Position conrod: BigEnd at crank pin, SmallEnd at wrist pin
		# Conrod rotates around its center, so position it at midpoint
		_conrod.position = (crank_pin + wrist_pin) / 2

func _get_crank_pin_position(theta: float) -> Vector3:
	"""Calculate crank pin position based on crank angle."""
	var x = R * sin(theta) * scale_3d
	var y = R * cos(theta) * scale_3d  # positive: pin goes UP at TDC (theta=0)
	var base = _crankshaft.position if _crankshaft else Vector3.ZERO
	return base + Vector3(x, y, 0.0)

func _update_reed_valve(state: Dictionary):
	"""Animate reed valve flex based on opening."""
	if not _reed:
		return
	
	var opening = state.get("reed_opening", 0.0)
	# Flex reed petals outward
	_reed.scale.x = 1.0 + opening * 0.3
	_reed.rotation.z = opening * 0.2

func _update_spark(state: Dictionary):
	"""Animate spark plug emission."""
	if not _spark:
		return
	
	var spark_on = state.get("spark_active", false)
	
	# Toggle spark light/emission
	var mat = _spark.get_active_material(0)
	if mat and mat is StandardMaterial3D:
		if spark_on:
			mat.emission = Color(1.0, 0.9, 0.5)
			mat.emission_energy = 5.0
		else:
			mat.emission = Color(0.0, 0.0, 0.0)
			mat.emission_energy = 0.0

func _update_effects(state: Dictionary):
	"""Update visual effects based on engine state."""
	var T_cyl = state.get("T_cyl", 293.0)
	var burn_frac = state.get("burn_fraction", 0.0)
	
	# Combustion glow
	if combustion_glow:
		var glow = get_node_or_null(combustion_glow)
		if glow and glow is OmniLight3D:
			if is_combusting:
				var intensity = burn_frac * 10.0
				glow.light_energy = intensity
				glow.visible = true
			else:
				glow.visible = false
	
	# Combustion fire particles: emit only while actively burning
	if exhaust_particles:
		var comb = get_node_or_null(exhaust_particles)
		if comb and comb is GPUParticles3D:
			comb.emitting = is_combusting
			comb.amount_ratio = clampf(burn_frac, 0.0, 1.0)
	
	# Gas flow particles: emit only while transfer port is open (a_tr > 0)
	if gas_flow_particles:
		var gas = get_node_or_null(gas_flow_particles)
		if gas and gas is GPUParticles3D:
			var a_tr = state.get("a_tr", 0.0)
			gas.emitting = a_tr > 0.0
			gas.amount_ratio = clampf(a_tr, 0.0, 1.0)

func _on_connected():
	print("Physics server connected - starting simulation")

func _on_disconnected():
	print("Physics server disconnected")
