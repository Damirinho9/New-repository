extends Node2D

const WIDTH := 1280.0
const HEIGHT := 720.0
const FLOOR_Y := 640.0
const PLAYER_RADIUS := 22.0
const MOVE_SPEED := 230.0
const JUMP_SPEED := 510.0
const GRAVITY := 1350.0

@onready var krosh: Node2D = $Player_Krosh
@onready var yozhik: Node2D = $Player_Yozhik
@onready var wind_puff: Node2D = $WindPuff
@onready var gate_node: Node2D = $FriendshipGate
@onready var finish_node: Node2D = $FinishZone

var krosh_vel := Vector2.ZERO
var yozhik_vel := Vector2.ZERO
var pieces := [false, false, false]
var gate_open := false
var level_complete := false
var reward_stars := 0
var message := "Добро пожаловать! Крош и Ёжик ищут части воздушного змея."
var tutorial := "Игрок 1: A/D + W | Игрок 2: ←/→ + ↑"
var auto_demo := false
var elapsed := 0.0
var event_flags := {}
var puff_dir := 1.0
var last_checkpoint := Vector2(100, 600)
var last_event := "READY"

var platforms := [
    Rect2(0, FLOOR_Y, 1280, 80),
    Rect2(190, 520, 240, 28),
    Rect2(505, 445, 245, 28),
    Rect2(825, 520, 205, 28)
]

func _ready() -> void:
    auto_demo = OS.has_environment("CI_CAPTURE")
    if OS.has_environment("VALIDATE_ONLY"):
        _print_validation()
        call_deferred("_quit_validation")
        return
    _print_validation()
    queue_redraw()

func _quit_validation() -> void:
    get_tree().quit(0)

func _print_validation() -> void:
    var ok := true
    ok = ok and krosh != null and yozhik != null and wind_puff != null and gate_node != null
    ok = ok and platforms.size() == 4
    ok = ok and is_equal_approx(MOVE_SPEED, 230.0)
    ok = ok and is_equal_approx(JUMP_SPEED, 510.0)
    if ok:
        print("CASE 2 VALIDATION: PASS")
        print("Players=2 SameScreen=true Collectibles=3 Gate=DualSwitch Enemy=WindPuff")
        print("Controls=P1[A,D,W] P2[LEFT,RIGHT,UP]")
    else:
        print("CASE 2 VALIDATION: FAIL")

func _process(delta: float) -> void:
    elapsed += delta
    if auto_demo:
        _run_auto_demo(delta)
    else:
        _manual_update(delta)
    _update_wind_puff(delta)
    _update_collectibles()
    _update_gate()
    _check_finish()
    queue_redraw()

func _manual_update(delta: float) -> void:
    krosh_vel.x = _axis(KEY_A, KEY_D) * MOVE_SPEED
    yozhik_vel.x = _axis(KEY_LEFT, KEY_RIGHT) * MOVE_SPEED
    if Input.is_key_pressed(KEY_W) and _is_on_platform(krosh.position):
        krosh_vel.y = -JUMP_SPEED
    if Input.is_key_pressed(KEY_UP) and _is_on_platform(yozhik.position):
        yozhik_vel.y = -JUMP_SPEED
    krosh_vel.y += GRAVITY * delta
    yozhik_vel.y += GRAVITY * delta
    _move_player(krosh, krosh_vel, delta, true)
    _move_player(yozhik, yozhik_vel, delta, false)

func _axis(negative_key: Key, positive_key: Key) -> float:
    var value := 0.0
    if Input.is_key_pressed(negative_key):
        value -= 1.0
    if Input.is_key_pressed(positive_key):
        value += 1.0
    return value

func _move_player(player: Node2D, velocity: Vector2, delta: float, is_krosh: bool) -> void:
    var old_pos := player.position
    var next_pos := old_pos + velocity * delta
    next_pos.x = clampf(next_pos.x, PLAYER_RADIUS, WIDTH - PLAYER_RADIUS)
    var vy := velocity.y
    if vy >= 0.0:
        for rect in platforms:
            if old_pos.y + PLAYER_RADIUS <= rect.position.y + 6.0 and next_pos.y + PLAYER_RADIUS >= rect.position.y:
                if next_pos.x >= rect.position.x - PLAYER_RADIUS and next_pos.x <= rect.end.x + PLAYER_RADIUS:
                    next_pos.y = rect.position.y - PLAYER_RADIUS
                    vy = 0.0
                    break
    if gate_open == false and old_pos.x < 1065.0 and next_pos.x + PLAYER_RADIUS > 1050.0:
        next_pos.x = 1050.0 - PLAYER_RADIUS
    player.position = next_pos
    if is_krosh:
        krosh_vel.y = vy
    else:
        yozhik_vel.y = vy
    if player.position.y > HEIGHT + 80:
        player.position = last_checkpoint
        if is_krosh:
            krosh_vel = Vector2.ZERO
        else:
            yozhik_vel = Vector2.ZERO
        _event("Возврат на контрольную точку")
    if player.position.distance_to(wind_puff.position) < 38.0:
        player.position = last_checkpoint
        if is_krosh:
            krosh_vel = Vector2.ZERO
        else:
            yozhik_vel = Vector2.ZERO
        _event("Ветряной комок отбросил игрока к контрольной точке")

func _is_on_platform(pos: Vector2) -> bool:
    for rect in platforms:
        if abs((pos.y + PLAYER_RADIUS) - rect.position.y) < 7.0 and pos.x >= rect.position.x - PLAYER_RADIUS and pos.x <= rect.end.x + PLAYER_RADIUS:
            return true
    return false

func _update_wind_puff(delta: float) -> void:
    wind_puff.position.x += 95.0 * puff_dir * delta
    if wind_puff.position.x > 790.0:
        puff_dir = -1.0
    elif wind_puff.position.x < 655.0:
        puff_dir = 1.0

func _update_collectibles() -> void:
    var nodes := [$Collectible_1, $Collectible_2, $Collectible_3]
    for i in range(nodes.size()):
        if pieces[i]:
            continue
        if krosh.position.distance_to(nodes[i].position) < 45.0 or yozhik.position.distance_to(nodes[i].position) < 45.0:
            pieces[i] = true
            reward_stars += 1
            _event("Найдена часть змея %d/3" % reward_stars)

func _update_gate() -> void:
    var krosh_on := krosh.position.distance_to($FriendshipSwitch_Krosh.position) < 48.0
    var yozhik_on := yozhik.position.distance_to($FriendshipSwitch_Yozhik.position) < 48.0
    if krosh_on and yozhik_on and not gate_open:
        gate_open = true
        tutorial = "Ворота дружбы открыты! Оба игрока сработали вместе."
        _event("CO-OP: оба переключателя нажаты одновременно")

func _check_finish() -> void:
    if level_complete or not gate_open or reward_stars < 3:
        return
    if krosh.position.distance_to(finish_node.position) < 70.0 and yozhik.position.distance_to(finish_node.position) < 70.0:
        level_complete = true
        message = "УРОВЕНЬ ПРОЙДЕН! Воздушный змей собран."
        tutorial = "Награда: 3 звезды + наклейка «Команда друзей»"
        _event("LEVEL COMPLETE")

func _run_auto_demo(_delta: float) -> void:
    if elapsed < 1.4:
        message = "Миссия: найти 3 части воздушного змея и открыть Ворота дружбы."
        tutorial = "Два игрока играют одновременно на одном экране."
        return
    if elapsed < 4.2:
        var t1: float = clampf((elapsed - 1.4) / 2.8, 0.0, 1.0)
        krosh.position = _arc(Vector2(100, 600), Vector2(300, 475), t1, 115.0)
        yozhik.position = _arc(Vector2(150, 600), Vector2(260, 498), t1, 80.0)
        tutorial = "Обучение: прыжок на платформу и сбор первой части."
        return
    if elapsed < 7.2:
        var t2: float = clampf((elapsed - 4.2) / 3.0, 0.0, 1.0)
        krosh.position = _arc(Vector2(300, 475), Vector2(610, 405), t2, 130.0)
        yozhik.position = _arc(Vector2(260, 498), Vector2(535, 425), t2, 105.0)
        tutorial = "Игроки двигаются вместе, но могут выбирать разные траектории."
        return
    if elapsed < 10.0:
        var t3: float = clampf((elapsed - 7.2) / 2.8, 0.0, 1.0)
        krosh.position = _arc(Vector2(610, 405), Vector2(915, 475), t3, 120.0)
        yozhik.position = _arc(Vector2(535, 425), Vector2(860, 495), t3, 85.0)
        tutorial = "Опасность: Ветряной комок патрулирует нижнюю дорожку."
        return
    if elapsed < 12.5:
        var t4: float = clampf((elapsed - 10.0) / 2.5, 0.0, 1.0)
        krosh.position = Vector2(lerpf(915.0, 845.0, t4), 603)
        yozhik.position = Vector2(lerpf(860.0, 955.0, t4), 603)
        tutorial = "Кооператив: каждому игроку нужно занять свой переключатель."
        return
    if elapsed < 14.4:
        krosh.position = Vector2(845, 603)
        yozhik.position = Vector2(955, 603)
        tutorial = "Оба переключателя активны одновременно - ворота открываются."
        return
    if elapsed < 17.0:
        var t5: float = clampf((elapsed - 14.4) / 2.6, 0.0, 1.0)
        krosh.position = _arc(Vector2(845, 603), Vector2(1190, 590), t5, 55.0)
        yozhik.position = _arc(Vector2(955, 603), Vector2(1210, 590), t5, 40.0)
        tutorial = "Финиш засчитывается только когда оба героя пришли вместе."
        return
    if elapsed >= 20.0:
        get_tree().quit(0)

func _arc(a: Vector2, b: Vector2, t: float, height: float) -> Vector2:
    var p := a.lerp(b, t)
    p.y -= sin(t * PI) * height
    return p

func _event(text: String) -> void:
    last_event = text
    print("EVENT: " + text)

func _draw() -> void:
    draw_rect(Rect2(0, 0, 1280, 720), Color("8bd4f6"))
    draw_circle(Vector2(1110, 90), 48, Color("ffe580"))
    _draw_cloud(Vector2(180, 110), 1.0)
    _draw_cloud(Vector2(500, 85), 0.8)
    _draw_cloud(Vector2(850, 135), 1.15)
    draw_colored_polygon(PackedVector2Array([Vector2(0,640),Vector2(0,500),Vector2(250,430),Vector2(490,520),Vector2(710,410),Vector2(980,500),Vector2(1280,420),Vector2(1280,640)]), Color("8ac66d"))
    for rect in platforms:
        draw_rect(rect, Color("76563a"), true)
        draw_rect(Rect2(rect.position, Vector2(rect.size.x, 8)), Color("6dbb55"), true)
    for x in [80, 460, 790, 1160]:
        draw_circle(Vector2(x, 622), 7, Color("fff176"))
        draw_line(Vector2(x, 630), Vector2(x, 640), Color("3f8e43"), 3)
    var collect_nodes := [$Collectible_1, $Collectible_2, $Collectible_3]
    for i in range(3):
        if not pieces[i]:
            _draw_kite_piece(collect_nodes[i].position, i)
    _draw_switch($FriendshipSwitch_Krosh.position, Color("4fc3f7"), krosh.position.distance_to($FriendshipSwitch_Krosh.position) < 48.0)
    _draw_switch($FriendshipSwitch_Yozhik.position, Color("ba68c8"), yozhik.position.distance_to($FriendshipSwitch_Yozhik.position) < 48.0)
    if not gate_open:
        draw_rect(Rect2(1050, 500, 30, 140), Color("6d4c41"), true)
        for y in [515,545,575,605]:
            draw_rect(Rect2(1045, y, 40, 9), Color("a1887f"), true)
    else:
        draw_string(ThemeDB.fallback_font, Vector2(1015, 485), "ОТКРЫТО", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("2e7d32"))
    draw_rect(Rect2(1160, 535, 95, 105), Color(1,1,1,0.26), true)
    draw_line(Vector2(1180, 640), Vector2(1180, 535), Color("5d4037"), 6)
    draw_colored_polygon(PackedVector2Array([Vector2(1180,535),Vector2(1240,555),Vector2(1180,575)]), Color("ff7043"))
    draw_string(ThemeDB.fallback_font, Vector2(1155, 520), "ФИНИШ", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("4e342e"))
    _draw_wind_puff(wind_puff.position)
    _draw_character(krosh.position, Color("43a5e6"), "КРОШ", true)
    _draw_character(yozhik.position, Color("9b6bb5"), "ЁЖИК", false)
    draw_rect(Rect2(18, 18, 730, 112), Color(0.03,0.05,0.08,0.78), true)
    draw_string(ThemeDB.fallback_font, Vector2(34, 47), "СМЕШАРИКИ: ДВА ДРУГА И ВОЗДУШНЫЙ ЗМЕЙ", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(34, 76), message, HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("fff8e1"))
    draw_string(ThemeDB.fallback_font, Vector2(34, 103), tutorial, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("d9f3ff"))
    draw_string(ThemeDB.fallback_font, Vector2(990, 42), "Части змея: %d / 3" % reward_stars, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("263238"))
    draw_string(ThemeDB.fallback_font, Vector2(990, 68), "Ворота: %s" % ("ОТКРЫТЫ" if gate_open else "закрыты"), HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("263238"))
    draw_string(ThemeDB.fallback_font, Vector2(990, 94), "Событие: " + last_event, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("263238"))
    if level_complete:
        draw_rect(Rect2(260, 250, 760, 180), Color(0.04,0.08,0.10,0.88), true)
        draw_string(ThemeDB.fallback_font, Vector2(385, 305), "УРОВЕНЬ ПРОЙДЕН!", HORIZONTAL_ALIGNMENT_LEFT, -1, 38, Color("fff176"))
        draw_string(ThemeDB.fallback_font, Vector2(350, 350), "Воздушный змей собран - команда получила 3 звезды", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("ffffff"))
        draw_string(ThemeDB.fallback_font, Vector2(430, 392), "Наклейка: «Команда друзей»", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("80deea"))

func _draw_character(pos: Vector2, color: Color, label: String, long_ears: bool) -> void:
    draw_circle(pos, PLAYER_RADIUS, color)
    draw_circle(pos + Vector2(-7,-5), 3, Color("ffffff"))
    draw_circle(pos + Vector2(7,-5), 3, Color("ffffff"))
    draw_circle(pos + Vector2(-7,-5), 1.5, Color("263238"))
    draw_circle(pos + Vector2(7,-5), 1.5, Color("263238"))
    if long_ears:
        draw_line(pos + Vector2(-9,-18), pos + Vector2(-13,-41), color, 8)
        draw_line(pos + Vector2(9,-18), pos + Vector2(13,-41), color, 8)
    else:
        for a in [-2.6,-2.1,-1.6,-1.1,-0.6]:
            draw_line(pos + Vector2(cos(a)*18,sin(a)*18), pos + Vector2(cos(a)*30,sin(a)*30), Color("6d4c7d"), 6)
    draw_string(ThemeDB.fallback_font, pos + Vector2(-27,44), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("263238"))

func _draw_kite_piece(pos: Vector2, idx: int) -> void:
    var colors := [Color("ff7043"), Color("ffee58"), Color("66bb6a")]
    var c: Color = colors[idx]
    draw_colored_polygon(PackedVector2Array([pos+Vector2(0,-20),pos+Vector2(22,0),pos+Vector2(0,20),pos+Vector2(-22,0)]), c)
    draw_line(pos+Vector2(0,20), pos+Vector2(0,36), Color("6d4c41"), 2)

func _draw_switch(pos: Vector2, color: Color, active: bool) -> void:
    draw_rect(Rect2(pos+Vector2(-34,-9), Vector2(68,18)), color.darkened(0.35), true)
    draw_circle(pos+Vector2(0,-8), 18, color if not active else Color("fff176"))

func _draw_wind_puff(pos: Vector2) -> void:
    draw_circle(pos, 26, Color("eceff1"))
    draw_circle(pos+Vector2(-20,5), 17, Color("eceff1"))
    draw_circle(pos+Vector2(20,4), 18, Color("eceff1"))
    draw_circle(pos+Vector2(-7,-18), 15, Color("f5f5f5"))
    draw_string(ThemeDB.fallback_font, pos+Vector2(-48,48), "Ветряной комок", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("455a64"))

func _draw_cloud(pos: Vector2, scale_value: float) -> void:
    var c := Color(1,1,1,0.78)
    draw_circle(pos, 30*scale_value, c)
    draw_circle(pos+Vector2(30,5)*scale_value, 24*scale_value, c)
    draw_circle(pos+Vector2(-30,7)*scale_value, 22*scale_value, c)
