class_name UIController
extends Control

## UI Controller - Updates dashboard with real-time engine data

signal throttle_changed(value: float)
signal ignition_angle_changed(angle: float)
signal ignition_toggled(enabled: bool)
signal fuel_toggled(cutoff: bool)
signal starter_pressed(pressed: bool)

@export var physics_bridge: NodePath
@export var status_label: NodePath
@export var rpm_label: NodePath
@export var pressure_label: NodePath
@export var temp_label: NodePath
@export var throttle_slider: NodePath
@export var ignition_slider: NodePath
@export var ignition_button: NodePath
@export var fuel_button: NodePath
@export var starter_button: NodePath

var _physics: Node = null
var _status: Label = null
var _rpm: Label = null
var _pressure: Label = null
var _temp: Label = null

func _ready():
	# Get references (use get_node_or_null for robustness)
	if physics_bridge:
		_physics = get_node_or_null(physics_bridge)
		if _physics:
			if _physics.has_signal("state_received"):
				_physics.connect("state_received", Callable(self, "_on_state_received"))
			if _physics.has_signal("connected"):
				_physics.connect("connected", Callable(self, "_on_connected"))
			if _physics.has_signal("disconnected"):
				_physics.connect("disconnected", Callable(self, "_on_disconnected"))
		else:
			print("Warning: UI physics_bridge node not found at: ", physics_bridge)
	
	_status = _find_node(status_label, "StatusLabel")
	_rpm = _find_node(rpm_label, "RPMLabel")
	_pressure = _find_node(pressure_label, "PressureLabel")
	_temp = _find_node(temp_label, "TempLabel")
	
	print("UI controller initialized (status=%s, rpm=%s)" % [_status != null, _rpm != null])
	
	# Connect UI controls
	var slider = _find_node(throttle_slider, "ThrottleSlider") as Slider
	if slider:
		slider.value_changed.connect(_on_throttle_changed)
	
	var ign_slider = _find_node(ignition_slider, "IgnitionSlider") as Slider
	if ign_slider:
		ign_slider.value_changed.connect(_on_ignition_angle_changed)
	
	var ign_btn = _find_node(ignition_button, "IgnitionButton") as Button
	if ign_btn:
		ign_btn.toggled.connect(_on_ignition_toggled)
	
	var fuel_btn = _find_node(fuel_button, "FuelButton") as Button
	if fuel_btn:
		fuel_btn.toggled.connect(_on_fuel_toggled)
	
	var start_btn = _find_node(starter_button, "StarterButton") as Button
	if start_btn:
		start_btn.button_down.connect(_on_starter_down)
		start_btn.button_up.connect(_on_starter_up)

func _find_node(path: NodePath, fallback_name: String) -> Node:
	"""Find node by path, falling back to recursive child search."""
	if path:
		var node = get_node_or_null(path)
		if node:
			return node
	return find_child(fallback_name, true, false)

func _on_state_received(state: Dictionary):
	"""Update UI with new physics state."""
	var rpm = state.get("rpm", 0)
	var p_cyl = state.get("p_cyl", 0.0) / 100000.0  # Pa to Bar
	var T_cyl = state.get("T_cyl", 293.0)
	var throttle = state.get("throttle", 0.0)
	var ignition = state.get("ignition_enabled", true)
	var fuel = state.get("fuel_cutoff", false)
	
	if _rpm:
		_rpm.text = "RPM: %d" % rpm
	
	if _pressure:
		_pressure.text = "Pressure: %.2f Bar" % p_cyl
	
	if _temp:
		_temp.text = "Temp: %.0f K" % T_cyl
	
	# Update sliders if different from local
	if throttle_slider:
		var slider = get_node(throttle_slider) as Slider
		if slider and abs(slider.value - throttle * 100) > 1:
			slider.value = throttle * 100

func _on_connected():
	if _status:
		_status.text = "Connected to physics server\nEngine ready"
		_status.modulate = Color(0.2, 0.8, 0.2, 1)

func _on_disconnected():
	if _status:
		_status.text = "Disconnected from physics server\nWaiting for connection..."
		_status.modulate = Color(0.8, 0.2, 0.2, 1)

func _on_throttle_changed(value: float):
	if _physics:
		_physics.set_throttle(value / 100.0)
	emit_signal("throttle_changed", value / 100.0)

func _on_ignition_angle_changed(value: float):
	if _physics:
		_physics.set_ignition_angle(value)
	emit_signal("ignition_angle_changed", value)

func _on_ignition_toggled(enabled: bool):
	if _physics:
		_physics.set_ignition_enabled(enabled)
	emit_signal("ignition_toggled", enabled)

func _on_fuel_toggled(cutoff: bool):
	if _physics:
		_physics.set_fuel_cutoff(cutoff)
	emit_signal("fuel_toggled", cutoff)

func _on_starter_down():
	if _physics:
		_physics.set_starter(true)
	emit_signal("starter_pressed", true)

func _on_starter_up():
	if _physics:
		_physics.set_starter(false)
	emit_signal("starter_pressed", false)

func _input(event):
	# Keyboard shortcuts
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_UP:
				if throttle_slider:
					var slider = get_node(throttle_slider) as Slider
					if slider:
						slider.value = min(slider.value + 5, 100)
			KEY_DOWN:
				if throttle_slider:
					var slider = get_node(throttle_slider) as Slider
					if slider:
						slider.value = max(slider.value - 5, 0)
			KEY_I:
				if ignition_button:
					var btn = get_node(ignition_button) as Button
					if btn:
						btn.button_pressed = !btn.button_pressed
			KEY_K:
				if fuel_button:
					var btn = get_node(fuel_button) as Button
					if btn:
						btn.button_pressed = !btn.button_pressed
			KEY_S:
				if event.pressed and starter_button:
					_on_starter_down()
	elif event is InputEventKey and not event.pressed and event.keycode == KEY_S:
		_on_starter_up()
