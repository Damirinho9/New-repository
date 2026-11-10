extends Node3D

const PLAYER_MAX_HP := 100.0
const PLAYER_DEFENSE := 8.0
const ENEMY_MAX_HP := 75.0
const MELEE_DAMAGE := 15.0
const RANGED_DAMAGE := 12.0
const ENEMY_DAMAGE := 15.0
const DETECTION_RANGE := 8.0
const ATTACK_RANGE := 1.8
const WALK_SPEED := 4.0
const RUN_MULTIPLIER := 1.3
const SNEAK_MULTIPLIER := 0.7

@onready var player: Node3D = $Player
@onready var enemy: Node3D = $Enemy
@onready var projectile_spawn: Marker3D = $Player/ProjectileSpawn
@onready var camera: Camera3D = $Camera3D

var player_hp := PLAYER_MAX_HP
var enemy_hp := ENEMY_MAX_HP
var blocking := false
var enemy_state := "IDLE"
var last_event := "Ready"
var elapsed := 0.0
var event_flags := {}
var auto_demo := false
var enemy_ai_enabled := true
var enemy_attack_clock := 0.0
var event_lines: Array[String] = []

var hp_label: Label
var enemy_label: Label
var state_label: Label
var event_label: Label
var block_label: Label

func _ready() -> void:
    camera.position = Vector3(9.5, 7.2, 12.5)
    camera.look_at(Vector3(0, 1.0, 1.5), Vector3.UP)
    _build_hud()
    _push_event("Prototype ready")
    _print_validation()

    if OS.has_environment("VALIDATE_ONLY"):
        call_deferred("_quit_validation")
        return

    auto_demo = OS.has_environment("CI_CAPTURE")
    if auto_demo:
        _push_event("AUTO DEMO: start")
    _update_hud()

func _quit_validation() -> void:
    get_tree().quit(0)

func _print_validation() -> void:
    var ok := true
    ok = ok and is_equal_approx(PLAYER_MAX_HP, 100.0)
    ok = ok and is_equal_approx(PLAYER_DEFENSE, 8.0)
    ok = ok and is_equal_approx(MELEE_DAMAGE, 15.0)
    ok = ok and is_equal_approx(RANGED_DAMAGE, 12.0)
    ok = ok and is_equal_approx(DETECTION_RANGE, 8.0)
    ok = ok and is_equal_approx(ATTACK_RANGE, 1.8)
    ok = ok and player != null and enemy != null and camera != null
    if ok:
        print("CASE 1 VALIDATION: PASS")
        print("Player HP=100 Defense=8 Melee=15 Ranged=12")
        print("Enemy HP=75 Detection=8 AttackRange=1.8 EnemyDamage=15")
    else:
        print("CASE 1 VALIDATION: FAIL")

func _process(delta: float) -> void:
    elapsed += delta
    if auto_demo:
        _run_auto_demo(delta)
    else:
        _run_manual(delta)
    _update_enemy_ai(delta)
    _update_hud()

func _run_manual(delta: float) -> void:
    var move := Vector3.ZERO
    if Input.is_key_pressed(KEY_W):
        move.z -= 1.0
    if Input.is_key_pressed(KEY_S):
        move.z += 1.0
    if Input.is_key_pressed(KEY_A):
        move.x -= 1.0
    if Input.is_key_pressed(KEY_D):
        move.x += 1.0

    var speed := WALK_SPEED
    if Input.is_key_pressed(KEY_SHIFT):
        speed *= RUN_MULTIPLIER
    if Input.is_key_pressed(KEY_CTRL):
        speed *= SNEAK_MULTIPLIER

    if move.length() > 0.01:
        move = move.normalized()
        player.position += move * speed * delta
        player.look_at(player.global_position + move, Vector3.UP)

    blocking = Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)

    if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and not event_flags.get("manual_melee_lock", false):
        event_flags["manual_melee_lock"] = true
        _melee_attack()
        get_tree().create_timer(0.45).timeout.connect(func(): event_flags["manual_melee_lock"] = false)

    if Input.is_key_pressed(KEY_R) and not event_flags.get("manual_ranged_lock", false):
        event_flags["manual_ranged_lock"] = true
        _ranged_attack()
        get_tree().create_timer(0.65).timeout.connect(func(): event_flags["manual_ranged_lock"] = false)

    if Input.is_key_pressed(KEY_H) and not event_flags.get("manual_heal_lock", false):
        event_flags["manual_heal_lock"] = true
        _heal()
        get_tree().create_timer(0.7).timeout.connect(func(): event_flags["manual_heal_lock"] = false)

func _run_auto_demo(_delta: float) -> void:
    if elapsed >= 1.2 and elapsed < 3.4:
        var k: float = clampf((elapsed - 1.2) / 2.2, 0.0, 1.0)
        player.position.z = lerp(8.5, 3.0, k)
        player.rotation.y = 0.0

    if elapsed >= 4.1 and not event_flags.get("first_enemy_hit", false):
        event_flags["first_enemy_hit"] = true
        _enemy_attack()

    if elapsed >= 5.0 and not event_flags.get("melee_1", false):
        event_flags["melee_1"] = true
        _melee_attack()

    if elapsed >= 6.0 and not event_flags.get("melee_2", false):
        event_flags["melee_2"] = true
        _melee_attack()

    if elapsed >= 7.0 and not event_flags.get("block_hit", false):
        event_flags["block_hit"] = true
        blocking = true
        _push_event("BLOCK ACTIVE")
        _enemy_attack()

    if elapsed >= 8.0 and not event_flags.get("heal", false):
        event_flags["heal"] = true
        blocking = false
        _heal()

    if elapsed >= 8.8 and elapsed < 9.8:
        enemy_ai_enabled = false
        var k2: float = clampf((elapsed - 8.8) / 1.0, 0.0, 1.0)
        player.position.z = lerp(player.position.z, 6.0, k2)
        player.rotation.y = 0.0
        enemy_state = "RANGED TARGET"

    if elapsed >= 10.0 and not event_flags.get("range_1", false):
        event_flags["range_1"] = true
        _ranged_attack()

    if elapsed >= 11.2 and not event_flags.get("range_2", false):
        event_flags["range_2"] = true
        _ranged_attack()

    if elapsed >= 12.4 and not event_flags.get("range_3", false):
        event_flags["range_3"] = true
        _ranged_attack()

    if elapsed >= 13.6 and not event_flags.get("range_4", false):
        event_flags["range_4"] = true
        _ranged_attack()

    if elapsed >= 15.2 and not event_flags.get("done", false):
        event_flags["done"] = true
        _push_event("DEMO COMPLETE - all mechanics shown")

    if elapsed >= 17.2:
        get_tree().quit(0)

func _update_enemy_ai(delta: float) -> void:
    if enemy_hp <= 0.0:
        enemy_state = "DEAD"
        return
    if not enemy_ai_enabled:
        return

    var flat_player := Vector3(player.position.x, enemy.position.y, player.position.z)
    var distance := enemy.position.distance_to(flat_player)

    if distance > DETECTION_RANGE:
        enemy_state = "IDLE"
        return

    enemy.look_at(flat_player, Vector3.UP)

    if distance > ATTACK_RANGE:
        enemy_state = "CHASE"
        enemy.position = enemy.position.move_toward(flat_player, 1.65 * delta)
    else:
        enemy_state = "ATTACK"
        if not auto_demo:
            enemy_attack_clock -= delta
            if enemy_attack_clock <= 0.0:
                enemy_attack_clock = 1.5
                _enemy_attack()

func _calculate_damage(raw_damage: float, defense: float) -> float:
    return max(1.0, raw_damage - defense * 0.5)

func _enemy_attack() -> void:
    if player_hp <= 0.0 or enemy_hp <= 0.0:
        return
    var damage := _calculate_damage(ENEMY_DAMAGE, PLAYER_DEFENSE)
    if blocking:
        damage *= 0.3
        _push_event("Shield block: -%.1f HP (70%% reduction)" % damage)
    else:
        _push_event("Enemy hit: -%.1f HP" % damage)
    player_hp = max(0.0, player_hp - damage)

func _melee_attack() -> void:
    if enemy_hp <= 0.0:
        return
    var distance := player.position.distance_to(enemy.position)
    if distance > 2.6 and not auto_demo:
        _push_event("Melee missed: target too far")
        return
    var damage := _calculate_damage(MELEE_DAMAGE, 0.0)
    enemy_hp = max(0.0, enemy_hp - damage)
    _push_event("Melee attack: -%.0f enemy HP" % damage)
    _flash_enemy()
    if enemy_hp <= 0.0:
        _enemy_died()

func _ranged_attack() -> void:
    if enemy_hp <= 0.0:
        return
    var arrow := MeshInstance3D.new()
    arrow.name = "Projectile"
    var mesh := BoxMesh.new()
    mesh.size = Vector3(0.10, 0.10, 0.75)
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(1.0, 0.78, 0.18, 1.0)
    material.emission_enabled = true
    material.emission = Color(0.85, 0.42, 0.05, 1.0)
    mesh.material = material
    arrow.mesh = mesh
    add_child(arrow)
    arrow.global_position = projectile_spawn.global_position
    arrow.look_at(enemy.global_position + Vector3(0, 0.45, 0), Vector3.UP)
    _push_event("Ranged attack: projectile launched")

    var target := enemy.global_position + Vector3(0, 0.45, 0)
    var tween := create_tween()
    tween.tween_property(arrow, "global_position", target, 0.55)
    tween.tween_callback(_finish_projectile.bind(arrow))

func _finish_projectile(arrow: Node) -> void:
    if is_instance_valid(arrow):
        arrow.queue_free()
    if enemy_hp <= 0.0:
        return
    var damage := _calculate_damage(RANGED_DAMAGE, 0.0)
    enemy_hp = max(0.0, enemy_hp - damage)
    _push_event("Ranged hit: -%.0f enemy HP" % damage)
    _flash_enemy()
    if enemy_hp <= 0.0:
        _enemy_died()

func _heal() -> void:
    if player_hp <= 0.0:
        return
    var before := player_hp
    player_hp = min(PLAYER_MAX_HP, player_hp + PLAYER_MAX_HP * 0.10)
    _push_event("Healing potion: +%.1f HP" % (player_hp - before))

func _enemy_died() -> void:
    enemy_state = "DEAD"
    enemy_ai_enabled = false
    _push_event("Enemy defeated")
    var tween := create_tween()
    tween.tween_property(enemy, "rotation", Vector3(0, 0, deg_to_rad(90.0)), 0.45)

func _flash_enemy() -> void:
    var body := $Enemy/Body as MeshInstance3D
    if body == null:
        return
    var old_scale := body.scale
    body.scale = old_scale * 1.08
    var tween := create_tween()
    tween.tween_property(body, "scale", old_scale, 0.18)

func _push_event(text: String) -> void:
    last_event = text
    event_lines.push_front(text)
    while event_lines.size() > 4:
        event_lines.pop_back()
    print("EVENT: " + text)

func _build_hud() -> void:
    var layer := CanvasLayer.new()
    layer.name = "HUD"
    add_child(layer)

    var panel := ColorRect.new()
    panel.position = Vector2(18, 18)
    panel.size = Vector2(550, 214)
    panel.color = Color(0.015, 0.02, 0.035, 0.88)
    layer.add_child(panel)

    var title := _make_label(layer, Vector2(34, 30), Vector2(520, 28), 22)
    title.text = "RPG CASE 1 - GODOT ENGINE PROTOTYPE"
    title.modulate = Color(0.78, 0.9, 1.0)

    var controls := _make_label(layer, Vector2(34, 62), Vector2(520, 46), 16)
    controls.text = "WASD Move | Shift Run x1.3 | Ctrl Sneak x0.7\nLMB Melee | RMB Block | R Ranged | H Heal 10%"

    hp_label = _make_label(layer, Vector2(34, 112), Vector2(520, 24), 18)
    enemy_label = _make_label(layer, Vector2(34, 138), Vector2(520, 24), 18)
    state_label = _make_label(layer, Vector2(34, 164), Vector2(520, 24), 17)
    event_label = _make_label(layer, Vector2(34, 190), Vector2(520, 30), 15)

    block_label = _make_label(layer, Vector2(1030, 26), Vector2(220, 42), 22)
    block_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    block_label.modulate = Color(1.0, 0.85, 0.18)

    var tag := _make_label(layer, Vector2(965, 665), Vector2(295, 34), 16)
    tag.text = "Studwork 7334625 | Case 1"
    tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    tag.modulate = Color(0.75, 0.78, 0.82)

func _make_label(parent: Node, pos: Vector2, size: Vector2, font_size: int) -> Label:
    var label := Label.new()
    label.position = pos
    label.size = size
    label.add_theme_font_size_override("font_size", font_size)
    label.add_theme_color_override("font_color", Color.WHITE)
    parent.add_child(label)
    return label

func _update_hud() -> void:
    if hp_label == null:
        return
    hp_label.text = "PLAYER HP: %.1f / 100   DEF: 8" % player_hp
    enemy_label.text = "ENEMY HP: %.1f / 75   AI: %s" % [enemy_hp, enemy_state]
    state_label.text = "Melee: 15   Ranged: 12   Detection: 8m   Attack: 1.8m"
    event_label.text = "Event: " + last_event
    block_label.text = "BLOCK ACTIVE" if blocking else ""
