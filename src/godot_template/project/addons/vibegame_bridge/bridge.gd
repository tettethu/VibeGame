extends Node

## VibeGame Godot runtime bridge (experimental).
##
## Speaks line-delimited JSON over TCP so the VibeGame CLI can drive a running
## Godot game the same way it drives the Phaser runtime: snapshot, screenshot,
## input injection, frame stepping and expression evaluation.
##
## `vibegame godot init` installs this node as the `VibeGameBridge` autoload.
## It listens on 127.0.0.1 only. The CLI chooses the port and passes
## `--vibegame-bridge=<port>` after `--` on the Godot command line.

const DEFAULT_PORT := 35700
const MAX_CONSOLE_ENTRIES := 500
const MAX_SNAPSHOT_NODES := 4000

const KEY_ALIASES := {
	"Space": KEY_SPACE,
	"Enter": KEY_ENTER,
	"Escape": KEY_ESCAPE,
	"Tab": KEY_TAB,
	"Backspace": KEY_BACKSPACE,
	"Delete": KEY_DELETE,
	"ArrowUp": KEY_UP,
	"ArrowDown": KEY_DOWN,
	"ArrowLeft": KEY_LEFT,
	"ArrowRight": KEY_RIGHT,
	"ShiftLeft": KEY_SHIFT,
	"ShiftRight": KEY_SHIFT,
	"ControlLeft": KEY_CTRL,
	"ControlRight": KEY_CTRL,
	"AltLeft": KEY_ALT,
	"AltRight": KEY_ALT,
	"Backquote": KEY_QUOTELEFT,
	"Minus": KEY_MINUS,
	"Equal": KEY_EQUAL,
	"BracketLeft": KEY_BRACKETLEFT,
	"BracketRight": KEY_BRACKETRIGHT,
	"Backslash": KEY_BACKSLASH,
	"Semicolon": KEY_SEMICOLON,
	"Quote": KEY_APOSTROPHE,
	"Comma": KEY_COMMA,
	"Period": KEY_PERIOD,
	"Slash": KEY_SLASH,
}

var _server := TCPServer.new()
var _peer: StreamPeerTCP = null
var _buffer := ""
var _pending_events: Array[InputEvent] = []
var _active := false
var _step_remaining := 0
var _console_entries: Array[Dictionary] = []
var _console_seq := 0
var _port := DEFAULT_PORT
var _snapshot_count := 0


func _ready() -> void:
	# Runtime control must keep working while the game tree is paused.
	process_mode = Node.PROCESS_MODE_ALWAYS
	if OS.get_environment("VIBEGAME_GODOT_CHECK") == "1":
		_run_project_check()
		return
	_port = _resolve_port()
	var err := _server.listen(_port, "127.0.0.1")
	if err != OK:
		push_error("[vibegame] bridge cannot listen on 127.0.0.1:%d (%s)" % [_port, error_string(err)])
		return
	print("[vibegame] bridge listening on 127.0.0.1:%d" % _port)
	_write_ready_file()


func _process(_delta: float) -> void:
	_service_connection()
	_flush_pending_events()
	if _step_remaining > 0:
		_step_remaining -= 1
		if _step_remaining == 0:
			get_tree().paused = true


## Game code can call `VibeGameBridge.log_line("...")` to expose a message
## through `vibegame play console`.
func log_line(message: Variant, level: String = "log") -> void:
	_console_entries.append({
		"seq": _console_seq,
		"level": level,
		"text": str(message),
		"time": Time.get_ticks_msec(),
	})
	_console_seq += 1
	while _console_entries.size() > MAX_CONSOLE_ENTRIES:
		_console_entries.pop_front()


## `vibegame godot check` boots the project with VIBEGAME_GODOT_CHECK=1. Loading
## every script and scene here compiles the ones the entry scene never reaches,
## with autoload names in scope, and finds scene references to missing files.
func _run_project_check() -> void:
	var paths: Array[String] = []
	_collect_checkable("res://", paths)
	var failed := 0
	for path in paths:
		var problem := _check_resource(path)
		if not problem.is_empty():
			failed += 1
			print("[vibegame-check] FAIL %s: %s" % [path, problem])
	print("[vibegame-check] DONE %d checked, %d failed" % [paths.size(), failed])


func _collect_checkable(dir: String, out: Array[String]) -> void:
	for file in DirAccess.get_files_at(dir):
		if file.ends_with(".gd") or file.ends_with(".tscn"):
			out.append(dir.path_join(file))
	for sub in DirAccess.get_directories_at(dir):
		if not sub.begins_with("."):
			_collect_checkable(dir.path_join(sub), out)


func _check_resource(path: String) -> String:
	# Dependency entries read "<uid>::<type>::<path>".
	for dependency in ResourceLoader.get_dependencies(path):
		var dependency_path := dependency.get_slice("::", 2)
		if dependency_path.is_empty() or not ResourceLoader.exists(dependency_path):
			return "missing dependency %s" % dependency
	# Default cache mode: re-loading this running script uncached crashes Godot,
	# and a cached resource has already compiled.
	var resource := ResourceLoader.load(path)
	if resource == null:
		return "failed to load"
	if resource is GDScript and not (resource as GDScript).can_instantiate():
		return "script does not compile"
	return ""


func _resolve_port() -> int:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--vibegame-bridge="):
			return int(arg.get_slice("=", 1))
	var env_port := OS.get_environment("VIBEGAME_GODOT_BRIDGE_PORT")
	if env_port.is_valid_int():
		return int(env_port)
	return DEFAULT_PORT


func _write_ready_file() -> void:
	var path := OS.get_environment("VIBEGAME_GODOT_READY_FILE")
	if path.is_empty():
		return
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(str(_port))
		file.close()


func _service_connection() -> void:
	if _peer != null and _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		_peer = null
		_buffer = ""
	if _server.is_connection_available():
		if _peer != null:
			_peer.disconnect_from_host()
		_peer = _server.take_connection()
		_peer.set_no_delay(true)
		_buffer = ""
	if _peer == null:
		return
	var available := _peer.get_available_bytes()
	if available <= 0:
		return
	_buffer += _peer.get_utf8_string(available)
	var newline := _buffer.find("\n")
	while newline >= 0:
		var line := _buffer.substr(0, newline)
		_buffer = _buffer.substr(newline + 1)
		if not line.strip_edges().is_empty():
			_handle_line(line)
		newline = _buffer.find("\n")


func _flush_pending_events() -> void:
	# One event per frame keeps press/release visible to per-frame input
	# polling (`Input.is_action_just_pressed`, Button release handling).
	if _pending_events.is_empty():
		return
	var event: InputEvent = _pending_events.pop_front()
	Input.parse_input_event(event)
	Input.flush_buffered_events()


func _handle_line(line: String) -> void:
	var parsed: Variant = JSON.parse_string(line)
	if typeof(parsed) != TYPE_DICTIONARY:
		_reply({"ok": false, "error": "request must be a JSON object"})
		return
	var req: Dictionary = parsed
	match str(req.get("cmd", "")):
		"ping":
			_reply({"ok": true, "engine": "godot", "version": Engine.get_version_info().string})
		"status":
			_reply(_status_payload())
		"snapshot":
			_reply({"ok": true, "snapshot": _snapshot(int(req.get("maxDepth", 8)))})
		"screenshot":
			_cmd_screenshot()
		"eval":
			_cmd_eval(req)
		"set":
			_cmd_set(req)
		"click":
			_cmd_click(req)
		"mousemove":
			_cmd_mousemove(req)
		"drag":
			_cmd_drag(req)
		"key":
			_cmd_key(req)
		"input":
			_cmd_input(req)
		"activate":
			_active = true
			_step_remaining = 0
			get_tree().paused = true
			_reply({"ok": true, "active": true, "paused": true})
		"deactivate":
			_active = false
			_step_remaining = 0
			get_tree().paused = false
			_reply({"ok": true, "active": false, "paused": false})
		"pause":
			_step_remaining = 0
			get_tree().paused = true
			_reply({"ok": true, "paused": true})
		"play":
			_step_remaining = 0
			get_tree().paused = false
			_reply({"ok": true, "paused": false})
		"continue":
			_cmd_continue(req)
		"refresh":
			_active = false
			_step_remaining = 0
			_pending_events.clear()
			get_tree().paused = false
			get_tree().reload_current_scene()
			_reply({"ok": true})
		"console_get":
			_cmd_console_get(req)
		"console_clear":
			_console_entries.clear()
			_reply({"ok": true})
		"network_get":
			_reply({"ok": true, "entries": [], "next": 0})
		"network_clear":
			_reply({"ok": true})
		_:
			_reply({"ok": false, "error": "unknown command: %s" % str(req.get("cmd", ""))})


func _status_payload() -> Dictionary:
	return {
		"ok": true,
		"engine": "godot",
		"active": _active,
		"paused": get_tree().paused,
		"mode": "paused" if get_tree().paused else "playing",
		"frame": Engine.get_process_frames(),
		"stepRemaining": _step_remaining,
	}


func _cmd_continue(req: Dictionary) -> void:
	var frames := int(req.get("frames", 60))
	if frames <= 0:
		_step_remaining = 0
		get_tree().paused = true
		_reply({"ok": true, "frames": 0, "paused": true})
		return
	_step_remaining = frames
	get_tree().paused = false
	_reply({"ok": true, "frames": frames, "paused": false})


func _cmd_screenshot() -> void:
	var viewport := get_viewport()
	if viewport == null:
		_reply({"ok": false, "error": "no viewport"})
		return
	var texture := viewport.get_texture()
	if texture == null:
		_reply({"ok": false, "error": "no viewport texture (headless mode cannot render screenshots)"})
		return
	var image := texture.get_image()
	if image == null or image.is_empty():
		_reply({"ok": false, "error": "empty viewport image (headless mode cannot render screenshots)"})
		return
	var png := image.save_png_to_buffer()
	_reply({
		"ok": true,
		"data": Marshalls.raw_to_base64(png),
		"width": image.get_width(),
		"height": image.get_height(),
	})


func _cmd_eval(req: Dictionary) -> void:
	var code := str(req.get("code", ""))
	if code.strip_edges().is_empty():
		_reply({"ok": false, "error": "code is required"})
		return
	var expr := Expression.new()
	var parse_error := expr.parse(code)
	if parse_error != OK:
		_reply({"ok": false, "error": "parse error: %s" % expr.get_error_text()})
		return
	var scene := get_tree().current_scene
	var base: Object = scene if scene != null else self
	var result: Variant = expr.execute([], base, true)
	if expr.has_execute_failed():
		_reply({"ok": false, "error": "execution failed: %s" % expr.get_error_text()})
		return
	_reply({"ok": true, "result": _json_safe(result)})


func _cmd_set(req: Dictionary) -> void:
	var node := _find_node(str(req.get("nodeId", "")))
	if node == null:
		_reply({"ok": false, "error": "node not found: %s" % str(req.get("nodeId", ""))})
		return
	var path := str(req.get("path", ""))
	if path.is_empty():
		_reply({"ok": false, "error": "path is required"})
		return
	var parts := path.split(".")
	var target: Object = node
	for index in range(parts.size() - 1):
		var next_value: Variant = target.get(parts[index])
		if next_value == null or not (next_value is Object):
			_reply({"ok": false, "error": "cannot descend into %s" % parts[index]})
			return
		target = next_value
	var prop := parts[parts.size() - 1]
	var previous: Variant = target.get(prop)
	var value: Variant = _coerce_value(previous, req.get("value", null))
	target.set(prop, value)
	_reply({"ok": true, "previous": _json_safe(previous), "value": _json_safe(target.get(prop))})


func _cmd_click(req: Dictionary) -> void:
	var x := float(req.get("x", 0.0))
	var y := float(req.get("y", 0.0))
	var button := _mouse_button_from(str(req.get("button", "left")))
	Input.warp_mouse(Vector2(x, y))
	_queue_mouse_button(x, y, button, true)
	_queue_mouse_button(x, y, button, false)
	_reply({"ok": true, "x": x, "y": y})


func _cmd_mousemove(req: Dictionary) -> void:
	var x := float(req.get("x", 0.0))
	var y := float(req.get("y", 0.0))
	Input.warp_mouse(Vector2(x, y))
	_queue_motion(x, y)
	_reply({"ok": true, "x": x, "y": y})


func _cmd_drag(req: Dictionary) -> void:
	var from := _point_from(req, "from", "fromX", "fromY")
	var to := _point_from(req, "to", "toX", "toY")
	var steps := clampi(int(req.get("steps", 10)), 1, 120)
	var button := _mouse_button_from(str(req.get("button", "left")))
	Input.warp_mouse(from)
	_queue_mouse_button(from.x, from.y, button, true)
	for index in range(1, steps + 1):
		var point := from.lerp(to, float(index) / float(steps))
		_queue_motion(point.x, point.y)
	_queue_mouse_button(to.x, to.y, button, false)
	_reply({"ok": true, "from": {"x": from.x, "y": from.y}, "to": {"x": to.x, "y": to.y}})


func _cmd_key(req: Dictionary) -> void:
	var code := str(req.get("key", ""))
	var key := _resolve_key(code)
	if key == KEY_NONE:
		_reply({"ok": false, "error": "unknown key: %s" % code})
		return
	match str(req.get("type", "press")):
		"down":
			_queue_key(key, true)
		"up":
			_queue_key(key, false)
		_:
			_queue_key(key, true)
			_queue_key(key, false)
	_reply({"ok": true, "key": code})


func _cmd_input(req: Dictionary) -> void:
	var action := str(req.get("action", ""))
	if action.is_empty():
		_reply({"ok": false, "error": "action is required"})
		return
	var known := InputMap.has_action(action)
	if req.has("held"):
		_queue_action(action, bool(req["held"]))
	else:
		_queue_action(action, true)
		_queue_action(action, false)
	_reply({"ok": true, "action": action, "known": known})


func _cmd_console_get(req: Dictionary) -> void:
	var since := int(req.get("since", 0))
	var level := str(req.get("level", ""))
	var entries: Array = []
	for entry in _console_entries:
		if int(entry.get("seq", 0)) < since:
			continue
		if not level.is_empty() and str(entry.get("level", "")) != level:
			continue
		entries.append(entry)
	_reply({"ok": true, "entries": entries, "next": _console_seq})


func _snapshot(max_depth: int) -> Dictionary:
	_snapshot_count = 0
	var scene := get_tree().current_scene
	var info := {
		"engine": "godot",
		"engineVersion": Engine.get_version_info().string,
		"scene": String(scene.name) if scene != null else "",
		"paused": get_tree().paused,
		"frame": Engine.get_process_frames(),
		"active": _active,
	}
	info["root"] = _node_info(get_tree().root, 0, maxi(max_depth, 1))
	return info


func _node_info(node: Node, depth: int, max_depth: int) -> Dictionary:
	_snapshot_count += 1
	var info := {
		"name": String(node.name),
		"type": node.get_class(),
		"path": str(node.get_path()),
	}
	if node is CanvasItem:
		info["visible"] = (node as CanvasItem).visible
	if node is Node2D:
		var node_2d := node as Node2D
		info["position"] = {"x": node_2d.position.x, "y": node_2d.position.y}
		info["rotation"] = node_2d.rotation
		info["scale"] = {"x": node_2d.scale.x, "y": node_2d.scale.y}
	if node is Control:
		var control := node as Control
		info["position"] = {"x": control.position.x, "y": control.position.y}
		info["size"] = {"w": control.size.x, "h": control.size.y}
	if node is BaseButton:
		var button := node as BaseButton
		info["disabled"] = button.disabled
		info["buttonPressed"] = button.button_pressed
	var text_value: Variant = node.get("text")
	if typeof(text_value) == TYPE_STRING:
		info["text"] = text_value
	var groups := node.get_groups()
	if not groups.is_empty():
		var group_names: Array[String] = []
		for group in groups:
			group_names.append(String(group))
		info["groups"] = group_names
	if node.has_method("vibegame_state"):
		var state: Variant = node.vibegame_state()
		if typeof(state) == TYPE_DICTIONARY:
			info["state"] = _json_safe(state)
	if depth < max_depth and _snapshot_count < MAX_SNAPSHOT_NODES:
		var children: Array = []
		for child in node.get_children():
			if _snapshot_count >= MAX_SNAPSHOT_NODES:
				break
			children.append(_node_info(child, depth + 1, max_depth))
		if not children.is_empty():
			info["children"] = children
	if _snapshot_count >= MAX_SNAPSHOT_NODES:
		info["truncated"] = true
	return info


func _find_node(node_id: String) -> Node:
	if node_id.is_empty():
		return get_tree().current_scene
	var direct := get_node_or_null(node_id)
	if direct != null:
		return direct
	var scene := get_tree().current_scene
	if scene == null:
		return null
	if String(scene.name) == node_id:
		return scene
	var relative := scene.get_node_or_null(node_id)
	if relative != null:
		return relative
	return scene.find_child(node_id, true, false)


func _point_from(req: Dictionary, nested_key: String, flat_x: String, flat_y: String) -> Vector2:
	if req.has(nested_key) and typeof(req[nested_key]) == TYPE_DICTIONARY:
		var point: Dictionary = req[nested_key]
		return Vector2(float(point.get("x", 0.0)), float(point.get("y", 0.0)))
	return Vector2(float(req.get(flat_x, 0.0)), float(req.get(flat_y, 0.0)))


func _mouse_button_from(name: String) -> MouseButton:
	match name.to_lower():
		"right":
			return MOUSE_BUTTON_RIGHT
		"middle":
			return MOUSE_BUTTON_MIDDLE
		_:
			return MOUSE_BUTTON_LEFT


func _resolve_key(code: String) -> Key:
	if KEY_ALIASES.has(code):
		return KEY_ALIASES[code]
	if code.begins_with("Key") and code.length() == 4:
		return OS.find_keycode_from_string(code.substr(3))
	if code.begins_with("Digit") and code.length() == 6:
		return OS.find_keycode_from_string(code.substr(5))
	if code.begins_with("Numpad") and code.length() == 7:
		return OS.find_keycode_from_string(code.substr(6))
	return OS.find_keycode_from_string(code)


func _queue_mouse_button(x: float, y: float, button: MouseButton, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.position = Vector2(x, y)
	event.global_position = Vector2(x, y)
	event.button_index = button
	event.pressed = pressed
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed and button == MOUSE_BUTTON_LEFT else 0
	_pending_events.append(event)


func _queue_motion(x: float, y: float) -> void:
	var event := InputEventMouseMotion.new()
	event.position = Vector2(x, y)
	event.global_position = Vector2(x, y)
	_pending_events.append(event)


func _queue_key(key: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = pressed
	_pending_events.append(event)


func _queue_action(action: String, pressed: bool) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = pressed
	event.strength = 1.0 if pressed else 0.0
	_pending_events.append(event)


func _coerce_value(previous: Variant, value: Variant) -> Variant:
	if previous is Vector2 and typeof(value) == TYPE_DICTIONARY:
		return Vector2(float(value.get("x", 0.0)), float(value.get("y", 0.0)))
	if previous is Vector2i and typeof(value) == TYPE_DICTIONARY:
		return Vector2i(int(value.get("x", 0)), int(value.get("y", 0)))
	if previous is Color and typeof(value) == TYPE_STRING:
		return Color(value)
	return value


func _json_safe(value: Variant) -> Variant:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STRING:
			return value
		TYPE_STRING_NAME:
			return String(value)
		TYPE_VECTOR2:
			return {"x": value.x, "y": value.y}
		TYPE_VECTOR2I:
			return {"x": value.x, "y": value.y}
		TYPE_COLOR:
			return value.to_html()
		TYPE_ARRAY:
			var array_out: Array = []
			for item in value:
				array_out.append(_json_safe(item))
			return array_out
		TYPE_DICTIONARY:
			var dict_out: Dictionary = {}
			for key in value:
				dict_out[str(key)] = _json_safe(value[key])
			return dict_out
		_:
			return str(value)


func _reply(payload: Dictionary) -> void:
	if _peer == null:
		return
	_peer.put_data((JSON.stringify(payload) + "\n").to_utf8_buffer())
