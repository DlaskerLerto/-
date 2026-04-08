import os
import random
import sqlite3
import logging
from flask import Flask, request, jsonify
import vk_api
from vk_api.utils import get_random_id

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN", "")
VK_SECRET = os.environ.get("VK_SECRET", "")
VK_CONFIRMATION = os.environ.get("VK_CONFIRMATION", "")

DB_PATH = "game.db"

# ─── GAME DATA ────────────────────────────────────────────────────────────────

ZONES = {
    1: {
        "name": "Приграничье",
        "temp": -5,
        "min_level": 1,
        "min_warmth": 0,
        "description": "Заброшенные сёла. Дымят костры. Здесь ещё можно выжить без спецснаряжения.",
        "enemies": ["Мародёр", "Одичавшая собака"],
        "loot_multiplier": 1.0,
    },
    2: {
        "name": "Ржавые пустоши",
        "temp": -18,
        "min_level": 3,
        "min_warmth": 20,
        "description": "Остовы заводов. Аномалии участились. Мародёры вооружены.",
        "enemies": ["Вооружённый мародёр", "Кровосос-падальщик", "Зомби-солдат"],
        "loot_multiplier": 1.8,
    },
    3: {
        "name": "Мёртвый город",
        "temp": -32,
        "min_level": 6,
        "min_warmth": 45,
        "description": "Вмёрзшие многоэтажки. Мутанты охраняют старые схроны.",
        "enemies": ["Псевдогигант", "Контролёр", "Химера"],
        "loot_multiplier": 3.0,
    },
    4: {
        "name": "Туманный провал",
        "temp": -49,
        "min_level": 10,
        "min_warmth": 70,
        "description": "Вечная метель. Видимость — ноль. Аномалии повсюду.",
        "enemies": ["Полтергейст", "Снорк-мутант", "Страж Зоны"],
        "loot_multiplier": 5.0,
    },
    5: {
        "name": "Ледяное сердце",
        "temp": -67,
        "min_level": 15,
        "min_warmth": 100,
        "description": "Эпицентр Зоны. Почти верная смерть без топ-снаряжения. Артефакты здесь — легенда.",
        "enemies": ["Монолитовец-фанатик", "Излом", "Вечный страж"],
        "loot_multiplier": 10.0,
    },
}

ENEMY_STATS = {
    "Мародёр":              {"hp": 30,  "dmg": (5, 12),  "exp": 15,  "tokens": (5, 15)},
    "Одичавшая собака":     {"hp": 20,  "dmg": (3, 8),   "exp": 10,  "tokens": (2, 8)},
    "Вооружённый мародёр":  {"hp": 50,  "dmg": (10, 20), "exp": 30,  "tokens": (15, 30)},
    "Кровосос-падальщик":   {"hp": 70,  "dmg": (15, 25), "exp": 45,  "tokens": (20, 40)},
    "Зомби-солдат":         {"hp": 60,  "dmg": (12, 22), "exp": 35,  "tokens": (18, 35)},
    "Псевдогигант":         {"hp": 150, "dmg": (25, 45), "exp": 100, "tokens": (50, 100)},
    "Контролёр":            {"hp": 100, "dmg": (20, 40), "exp": 80,  "tokens": (40, 80)},
    "Химера":               {"hp": 120, "dmg": (30, 50), "exp": 90,  "tokens": (45, 90)},
    "Полтергейст":          {"hp": 80,  "dmg": (35, 55), "exp": 120, "tokens": (70, 130)},
    "Снорк-мутант":         {"hp": 110, "dmg": (30, 50), "exp": 110, "tokens": (60, 120)},
    "Страж Зоны":           {"hp": 200, "dmg": (40, 65), "exp": 180, "tokens": (100, 180)},
    "Монолитовец-фанатик":  {"hp": 180, "dmg": (50, 80), "exp": 250, "tokens": (150, 280)},
    "Излом":                {"hp": 250, "dmg": (60, 90), "exp": 300, "tokens": (180, 320)},
    "Вечный страж":         {"hp": 350, "dmg": (70, 110),"exp": 500, "tokens": (300, 500)},
}

SHOP_ITEMS = {
    "Бинт":              {"price": 10,  "type": "heal",   "value": 20,  "warmth": 0,   "desc": "Восстанавливает 20 HP"},
    "Аптечка":           {"price": 30,  "type": "heal",   "value": 60,  "warmth": 0,   "desc": "Восстанавливает 60 HP"},
    "Армейская аптечка": {"price": 80,  "type": "heal",   "value": 150, "warmth": 0,   "desc": "Восстанавливает 150 HP"},
    "Телогрейка":        {"price": 40,  "type": "armor",  "value": 5,   "warmth": 15,  "desc": "+5 защиты, +15 тепла"},
    "Зимний костюм":     {"price": 120, "type": "armor",  "value": 12,  "warmth": 35,  "desc": "+12 защиты, +35 тепла"},
    "Экзоскелет-С":      {"price": 500, "type": "armor",  "value": 30,  "warmth": 70,  "desc": "+30 защиты, +70 тепла"},
    "Криокостюм":        {"price": 1200,"type": "armor",  "value": 50,  "warmth": 100, "desc": "+50 защиты, +100 тепла"},
    "Ржавый пистолет":   {"price": 50,  "type": "weapon", "value": 15,  "warmth": 0,   "desc": "+15 урона"},
    "АКС-74У":           {"price": 200, "type": "weapon", "value": 35,  "warmth": 0,   "desc": "+35 урона"},
    "Снайперка СВД":     {"price": 600, "type": "weapon", "value": 70,  "warmth": 0,   "desc": "+70 урона"},
    "Гаусс-пушка":       {"price": 2000,"type": "weapon", "value": 150, "warmth": 0,   "desc": "+150 урона"},
    "Стимулятор":        {"price": 25,  "type": "buff",   "value": 20,  "warmth": 0,   "desc": "+20 урона на следующий бой"},
}

NPCS = {
    "Сидорович": {
        "zone": 1,
        "greeting": "Сидорович смотрит из-под прилавка.\n— Чего надо, сталкер? Не стой, не мешай торговать.",
        "quests": ["q1_first_blood", "q2_dog_pelts"],
    },
    "Доктор Холод": {
        "zone": 2,
        "greeting": "Старик в обледенелом халате листает журнал.\n— Аномалии меняются. Я изучаю. Ты можешь помочь.",
        "quests": ["q3_anomaly_scan", "q4_rare_artifact"],
    },
    "Полковник Мороз": {
        "zone": 3,
        "greeting": "Военный у костра. Взгляд — как прицел.\n— Есть задание. Опасное. Платим жетонами.",
        "quests": ["q5_clear_outpost"],
    },
}

QUESTS = {
    "q1_first_blood": {
        "name": "Первая кровь",
        "npc": "Сидорович",
        "desc": "Убей 3 мародёров в Приграничье.",
        "goal_type": "kill",
        "goal_enemy": "Мародёр",
        "goal_count": 3,
        "reward_tokens": 60,
        "reward_exp": 50,
    },
    "q2_dog_pelts": {
        "name": "Шкуры для тепла",
        "npc": "Сидорович",
        "desc": "Убей 5 одичавших собак. Их шкуры пригодятся.",
        "goal_type": "kill",
        "goal_enemy": "Одичавшая собака",
        "goal_count": 5,
        "reward_tokens": 80,
        "reward_exp": 70,
    },
    "q3_anomaly_scan": {
        "name": "Данные аномалий",
        "npc": "Доктор Холод",
        "desc": "Выживи в 3 боях на Ржавых пустошах.",
        "goal_type": "survive_zone",
        "goal_zone": 2,
        "goal_count": 3,
        "reward_tokens": 150,
        "reward_exp": 120,
    },
    "q4_rare_artifact": {
        "name": "Редкий артефакт",
        "npc": "Доктор Холод",
        "desc": "Убей Химеру в Мёртвом городе.",
        "goal_type": "kill",
        "goal_enemy": "Химера",
        "goal_count": 1,
        "reward_tokens": 300,
        "reward_exp": 200,
    },
    "q5_clear_outpost": {
        "name": "Зачистка поста",
        "npc": "Полковник Мороз",
        "desc": "Уничтожь 2 Стражей Зоны в Туманном провале.",
        "goal_type": "kill",
        "goal_enemy": "Страж Зоны",
        "goal_count": 2,
        "reward_tokens": 600,
        "reward_exp": 400,
    },
}

EXP_TABLE = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200, 4000,
             5000, 6200, 7600, 9200, 11000, 13200, 15700, 18500, 21600, 25000]

# ─── DATABASE ─────────────────────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        vk_id       INTEGER PRIMARY KEY,
        name        TEXT,
        state       TEXT DEFAULT 'main',
        zone        INTEGER DEFAULT 1,
        hp          INTEGER DEFAULT 100,
        max_hp      INTEGER DEFAULT 100,
        level       INTEGER DEFAULT 1,
        exp         INTEGER DEFAULT 0,
        tokens      INTEGER DEFAULT 50,
        attack      INTEGER DEFAULT 10,
        defense     INTEGER DEFAULT 0,
        warmth      INTEGER DEFAULT 0,
        weapon      TEXT DEFAULT '',
        armor       TEXT DEFAULT '',
        inventory   TEXT DEFAULT '',
        active_quest TEXT DEFAULT '',
        quest_progress INTEGER DEFAULT 0,
        completed_quests TEXT DEFAULT '',
        battle_enemy TEXT DEFAULT '',
        battle_enemy_hp INTEGER DEFAULT 0,
        battle_buff  INTEGER DEFAULT 0
    )""")
    con.commit()
    con.close()

def get_player(vk_id):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = con.cursor()
    c.execute("SELECT * FROM players WHERE vk_id=?", (vk_id,))
    row = c.fetchone()
    con.close()
    return dict(row) if row else None

def save_player(p):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    fields = [k for k in p if k != "vk_id"]
    sql = "UPDATE players SET " + ", ".join(f"{f}=?" for f in fields) + " WHERE vk_id=?"
    c.execute(sql, [p[f] for f in fields] + [p["vk_id"]])
    con.commit()
    con.close()

def create_player(vk_id, name):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("INSERT INTO players (vk_id, name) VALUES (?, ?)", (vk_id, name))
    con.commit()
    con.close()
    return get_player(vk_id)

# ─── VK HELPERS ───────────────────────────────────────────────────────────────

def send(vk, peer_id, text, keyboard=None):
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": get_random_id(),
    }
    if keyboard:
        import json
        params["keyboard"] = json.dumps(keyboard)
    vk.messages.send(**params)

def kb(buttons, one_time=False, inline=False):
    rows = []
def kb(buttons, one_time=False, inline=False):
    rows = []
    for row in buttons:
        r = []
        for btn in row:
            label, color = btn if isinstance(btn, tuple) else (btn, "secondary")
            r.append({
                "action": {"type": "text", "label": label[:40], "payload": "{}"},
                "color": color
            })
        rows.append(r)
    return {"one_time": one_time, "inline": inline, "buttons": rows}}

# ─── LEVEL SYSTEM ─────────────────────────────────────────────────────────────

def exp_for_next(level):
    if level >= len(EXP_TABLE) - 1:
        return 999999
    return EXP_TABLE[level]

def try_levelup(p):
    msgs = []
    while p["exp"] >= exp_for_next(p["level"]):
        p["exp"] -= exp_for_next(p["level"])
        p["level"] += 1
        p["max_hp"] += 20
        p["hp"] = p["max_hp"]
        p["attack"] += 5
        msgs.append(f"⬆️ Уровень повышен! Теперь ты {p['level']} ур.\n+20 макс.HP, +5 атаки")
    return msgs

# ─── SCREENS ──────────────────────────────────────────────────────────────────

def screen_main(vk, p):
    zone = ZONES[p["zone"]]
    hp_bar = "❤️" * (p["hp"] // 20) + "🖤" * ((p["max_hp"] - p["hp"]) // 20)
    text = (
        f"👤 {p['name']} | Ур.{p['level']} | {p['tokens']} жетонов\n"
        f"❤️ {p['hp']}/{p['max_hp']} {hp_bar}\n"
        f"🌡 {zone['temp']}°C | 📍 {zone['name']}\n"
        f"────────────────\n"
        f"{zone['description']}"
    )
    keyboard = kb([
        [("⚔️ В бой", "negative"), ("🗺 Сменить зону", "primary")],
        [("🏪 Магазин", "positive"), ("💬 NPC", "primary")],
        [("📋 Квесты", "secondary"), ("🎒 Инвентарь", "secondary")],
        [("📊 Статус", "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def screen_status(vk, p):
    weapon = p["weapon"] or "Кулаки"
    armor = p["armor"] or "Нет"
    text = (
        f"📊 ДОСЬЕ: {p['name']}\n"
        f"────────────────\n"
        f"Уровень: {p['level']}\n"
        f"Опыт: {p['exp']} / {exp_for_next(p['level'])}\n"
        f"HP: {p['hp']} / {p['max_hp']}\n"
        f"Атака: {p['attack']}\n"
        f"Защита: {p['defense']}\n"
        f"Тепло: {p['warmth']}\n"
        f"Жетоны: {p['tokens']}\n"
        f"Оружие: {weapon}\n"
        f"Броня: {armor}\n"
        f"Зона: {ZONES[p['zone']]['name']}"
    )
    keyboard = kb([[("◀️ Назад", "secondary")]])
    send(vk, p["vk_id"], text, keyboard)

def screen_zones(vk, p):
    text = "🗺 ВЫБОР ЗОНЫ\n────────────────\n"
    btns = []
    for zid, z in ZONES.items():
        lock = ""
        if p["level"] < z["min_level"]:
            lock = f" 🔒 ур.{z['min_level']}"
        elif p["warmth"] < z["min_warmth"]:
            lock = f" 🥶 тепло {z['min_warmth']}"
        text += f"{zid}. {z['name']} ({z['temp']}°C){lock}\n"
        label = f"{'✅' if p['zone']==zid else '📍'} {z['name']}{lock}"
        btns.append([(label, "positive" if p["zone"] == zid else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_shop(vk, p):
    text = f"🏪 МАГАЗИН СИДОРОВИЧА\nЖетоны: {p['tokens']}\n────────────────\n"
    for name, item in SHOP_ITEMS.items():
        text += f"{name} — {item['price']} жт. | {item['desc']}\n"
    btns = []
    row = []
    for i, name in enumerate(SHOP_ITEMS):
        row.append((f"Купить: {name}", "secondary"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_inventory(vk, p):
    inv = p["inventory"].split(",") if p["inventory"] else []
    inv_counts = {}
    for item in inv:
        inv_counts[item] = inv_counts.get(item, 0) + 1
    text = f"🎒 ИНВЕНТАРЬ\nЖетоны: {p['tokens']}\n────────────────\n"
    if inv_counts:
        for item, cnt in inv_counts.items():
            text += f"• {item} x{cnt}\n"
    else:
        text += "Пусто.\n"
    btns = []
    healables = [i for i in inv_counts if SHOP_ITEMS.get(i, {}).get("type") == "heal"]
    for item in healables:
        btns.append([(f"Использовать: {item}", "positive")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_npcs(vk, p):
    available = {name: npc for name, npc in NPCS.items() if npc["zone"] <= p["zone"]}
    if not available:
        send(vk, p["vk_id"], "Здесь никого нет.", kb([[("◀️ Назад", "secondary")]]))
        return
    text = "💬 NPC В ОКРУГЕ\n────────────────\n"
    for name in available:
        text += f"• {name}\n"
    btns = [[name] for name in available]
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_npc_talk(vk, p, npc_name):
    npc = NPCS.get(npc_name)
    if not npc:
        screen_main(vk, p)
        return
    text = f"💬 {npc_name}\n────────────────\n{npc['greeting']}"
    completed = p["completed_quests"].split(",") if p["completed_quests"] else []
    available_q = [q for q in npc["quests"] if q not in completed]
    btns = []
    for qid in available_q:
        q = QUESTS[qid]
        btns.append([(f"📋 {q['name']}", "primary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_quests(vk, p):
    completed = p["completed_quests"].split(",") if p["completed_quests"] else []
    active = p["active_quest"]
    text = "📋 КВЕСТЫ\n────────────────\n"
    if active and active in QUESTS:
        q = QUESTS[active]
        text += f"▶️ АКТИВНЫЙ: {q['name']}\n{q['desc']}\nПрогресс: {p['quest_progress']}/{q['goal_count']}\n────────────────\n"
    done = [QUESTS[q]["name"] for q in completed if q in QUESTS]
    if done:
        text += "✅ Выполнены:\n" + "\n".join(f"• {n}" for n in done)
    else:
        text += "Нет выполненных квестов."
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def start_battle(vk, p):
    zone = ZONES[p["zone"]]
    enemy_name = random.choice(zone["enemies"])
    stats = ENEMY_STATS[enemy_name]
    p["battle_enemy"] = enemy_name
    p["battle_enemy_hp"] = stats["hp"]
    p["state"] = "battle"
    save_player(p)
    text = (
        f"⚔️ ВСТРЕЧА\n────────────────\n"
        f"Из темноты появляется: {enemy_name}\n"
        f"HP врага: {stats['hp']}\n"
        f"────────────────\n"
        f"Твой HP: {p['hp']}/{p['max_hp']}"
    )
    keyboard = kb([
        [("🗡 Атаковать", "negative"), ("🏃 Убежать", "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def do_attack(vk, p):
    enemy_name = p["battle_enemy"]
    stats = ENEMY_STATS[enemy_name]
    player_dmg = p["attack"] + p["battle_buff"] + random.randint(-3, 5)
    player_dmg = max(1, player_dmg)
    p["battle_enemy_hp"] -= player_dmg
    p["battle_buff"] = 0

    if p["battle_enemy_hp"] <= 0:
        # Victory
        mult = ZONES[p["zone"]]["loot_multiplier"]
        exp_gain = int(stats["exp"] * mult)
        tokens_gain = int(random.randint(*stats["tokens"]) * mult)
        p["tokens"] += tokens_gain
        p["exp"] += exp_gain

        quest_msg = update_quest_progress(p, enemy_name)
        levelup_msgs = try_levelup(p)

        p["state"] = "main"
        p["battle_enemy"] = ""
        p["battle_enemy_hp"] = 0
        save_player(p)

        text = (
            f"💀 {enemy_name} уничтожен!\n"
            f"────────────────\n"
            f"+{exp_gain} опыта | +{tokens_gain} жетонов\n"
        )
        if quest_msg:
            text += f"\n{quest_msg}"
        for lm in levelup_msgs:
            text += f"\n{lm}"
        send(vk, p["vk_id"], text, kb([[("⚔️ Ещё раз", "negative"), ("◀️ В лагерь", "secondary")]]))
        return

    # Enemy attacks
    enemy_dmg = random.randint(*stats["dmg"])
    enemy_dmg = max(0, enemy_dmg - p["defense"])
    p["hp"] -= enemy_dmg

    if p["hp"] <= 0:
        p["hp"] = 1
        p["tokens"] = max(0, p["tokens"] - int(p["tokens"] * 0.1))
        p["state"] = "main"
        p["battle_enemy"] = ""
        p["battle_enemy_hp"] = 0
        save_player(p)
        text = (
            f"💔 Ты потерял сознание...\n"
            f"────────────────\n"
            f"Очнулся у костра. HP восстановлен до 1.\n"
            f"Потеряно 10% жетонов."
        )
        send(vk, p["vk_id"], text, kb([[("◀️ В лагерь", "secondary")]]))
        return

    save_player(p)
    text = (
        f"⚔️ БОЙ\n────────────────\n"
        f"Ты нанёс {player_dmg} урона → HP врага: {p['battle_enemy_hp']}\n"
        f"{enemy_name} атаковал на {enemy_dmg} → Твой HP: {p['hp']}/{p['max_hp']}"
    )
    keyboard = kb([
        [("🗡 Атаковать", "negative"), ("🏃 Убежать", "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def update_quest_progress(p, killed_enemy=None, zone=None):
    qid = p["active_quest"]
    if not qid or qid not in QUESTS:
        return ""
    q = QUESTS[qid]
    if q["goal_type"] == "kill" and killed_enemy == q["goal_enemy"]:
        p["quest_progress"] += 1
    elif q["goal_type"] == "survive_zone" and zone == q.get("goal_zone"):
        p["quest_progress"] += 1

    if p["quest_progress"] >= q["goal_count"]:
        p["tokens"] += q["reward_tokens"]
        p["exp"] += q["reward_exp"]
        completed = p["completed_quests"].split(",") if p["completed_quests"] else []
        completed.append(qid)
        p["completed_quests"] = ",".join(filter(None, completed))
        p["active_quest"] = ""
        p["quest_progress"] = 0
        return (
            f"✅ КВЕСТ ВЫПОЛНЕН: {q['name']}\n"
            f"+{q['reward_tokens']} жетонов | +{q['reward_exp']} опыта"
        )
    return f"📋 Квест «{q['name']}»: {p['quest_progress']}/{q['goal_count']}"

# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────

def handle_message(vk, vk_id, text):
    text = text.strip()
    p = get_player(vk_id)

    # New player
    if not p:
        if p is None:
            send(vk, vk_id,
                 "❄️ ЗОНА. ЯДЕРНАЯ ЗИМА.\n────────────────\nТемпература падает. Мародёры рыщут.\nТы — сталкер. Последний шанс выжить.\n\nКак тебя зовут, сталкер?",
                 kb([[("Начать", "positive")]]))
            # Temporarily store state outside DB since player doesn't exist yet
            # We use a simple trick: create player with placeholder
            create_player(vk_id, "__new__")
            p = get_player(vk_id)
            p["state"] = "enter_name"
            save_player(p)
            return

    state = p["state"]

    # Name entry
    if state == "enter_name":
        if text == "Начать":
            send(vk, vk_id, "Введи своё имя, сталкер:")
            return
        name = text[:20].strip()
        if len(name) < 2:
            send(vk, vk_id, "Имя слишком короткое. Попробуй ещё раз.")
            return
        p["name"] = name
        p["state"] = "main"
        save_player(p)
        send(vk, vk_id,
             f"Добро пожаловать в Зону, {name}.\nТемпература за бортом: -5°C. Удачи.",
             None)
        screen_main(vk, p)
        return

    # Battle state
    if state == "battle":
        if text == "🗡 Атаковать":
            do_attack(vk, p)
        elif text == "🏃 Убежать":
            p["state"] = "main"
            p["battle_enemy"] = ""
            p["battle_enemy_hp"] = 0
            save_player(p)
            send(vk, p["vk_id"], "Ты отступил в темноту.", None)
            screen_main(vk, p)
        return

    # Main state routing
    if text in ("◀️ Назад", "В лагерь", "◀️ В лагерь"):
        screen_main(vk, p)
    elif text == "📊 Статус":
        screen_status(vk, p)
    elif text == "🗺 Сменить зону":
        screen_zones(vk, p)
    elif text == "🏪 Магазин":
        screen_shop(vk, p)
    elif text == "🎒 Инвентарь":
        screen_inventory(vk, p)
    elif text == "💬 NPC":
        screen_npcs(vk, p)
    elif text == "📋 Квесты":
        screen_quests(vk, p)
    elif text == "⚔️ В бой" or text == "⚔️ Ещё раз":
        zone = ZONES[p["zone"]]
        if p["level"] < zone["min_level"]:
            send(vk, vk_id, f"Недостаточный уровень. Нужен {zone['min_level']} ур.", None)
            screen_main(vk, p)
        elif p["warmth"] < zone["min_warmth"]:
            send(vk, vk_id, f"Слишком холодно. Нужно тепло {zone['min_warmth']}. Купи снаряжение.", None)
            screen_main(vk, p)
        else:
            start_battle(vk, p)

    # Zone selection
    elif text.startswith("📍") or text.startswith("✅"):
        for zid, z in ZONES.items():
            if z["name"] in text:
                if p["level"] < z["min_level"]:
                    send(vk, vk_id, f"🔒 Нужен {z['min_level']} уровень.", None)
                elif p["warmth"] < z["min_warmth"]:
                    send(vk, vk_id, f"🥶 Нужно тепло {z['min_warmth']}. Купи снаряжение.", None)
                else:
                    p["zone"] = zid
                    save_player(p)
                    send(vk, vk_id, f"Перемещаешься в: {z['name']}\n{z['temp']}°C. Будь осторожен.", None)
                    screen_main(vk, p)
                return

    # Shop purchase
    elif text.startswith("Купить: "):
        item_name = text[8:]
        item = SHOP_ITEMS.get(item_name)
        if not item:
            screen_main(vk, p)
            return
        if p["tokens"] < item["price"]:
            send(vk, vk_id, f"Не хватает жетонов. Нужно {item['price']}, у тебя {p['tokens']}.", None)
            screen_shop(vk, p)
            return
        p["tokens"] -= item["price"]
        if item["type"] == "heal":
            inv = p["inventory"].split(",") if p["inventory"] else []
            inv.append(item_name)
            p["inventory"] = ",".join(filter(None, inv))
            send(vk, vk_id, f"✅ Куплено: {item_name}. Лежит в рюкзаке.", None)
        elif item["type"] == "weapon":
            p["attack"] = 10 + item["value"]
            p["weapon"] = item_name
            send(vk, vk_id, f"✅ Вооружён: {item_name}. Атака: {p['attack']}.", None)
        elif item["type"] == "armor":
            old_warmth = SHOP_ITEMS.get(p["armor"], {}).get("warmth", 0)
            old_def = SHOP_ITEMS.get(p["armor"], {}).get("value", 0)
            p["defense"] = item["value"]
            p["warmth"] = item["warmth"]
            p["armor"] = item_name
            send(vk, vk_id, f"✅ Надета: {item_name}. Защита: {p['defense']}, Тепло: {p['warmth']}.", None)
        elif item["type"] == "buff":
            p["battle_buff"] = item["value"]
            send(vk, vk_id, f"✅ Использован: {item_name}. +{item['value']} атаки в следующем бою.", None)
        save_player(p)
        screen_shop(vk, p)

    # Use inventory item
    elif text.startswith("Использовать: "):
        item_name = text[14:]
        item = SHOP_ITEMS.get(item_name)
        inv = p["inventory"].split(",") if p["inventory"] else []
        if item_name not in inv or not item:
            send(vk, vk_id, "Предмет не найден.", None)
            screen_inventory(vk, p)
            return
        inv.remove(item_name)
        p["inventory"] = ",".join(filter(None, inv))
        if item["type"] == "heal":
            old_hp = p["hp"]
            p["hp"] = min(p["max_hp"], p["hp"] + item["value"])
            send(vk, vk_id, f"💊 {item_name} использован. HP: {old_hp} → {p['hp']}", None)
        save_player(p)
        screen_inventory(vk, p)

    # NPC talk
    elif text in NPCS:
        screen_npc_talk(vk, p, text)

    # Quest accept
    elif text.startswith("📋 "):
        quest_name = text[3:]
        qid = next((q for q, data in QUESTS.items() if data["name"] == quest_name), None)
        if not qid:
            screen_main(vk, p)
            return
        if p["active_quest"]:
            send(vk, vk_id, "У тебя уже есть активный квест. Сначала заверши его.", None)
            return
        p["active_quest"] = qid
        p["quest_progress"] = 0
        save_player(p)
        q = QUESTS[qid]
        send(vk, vk_id,
             f"📋 КВЕСТ ПРИНЯТ: {q['name']}\n────────────────\n{q['desc']}\n\nНаграда: {q['reward_tokens']} жт. + {q['reward_exp']} опыта",
             kb([[("◀️ Назад", "secondary")]]))

    else:
        screen_main(vk, p)

# ─── FLASK WEBHOOK ────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return "bad request", 400

    if data.get("secret") != VK_SECRET:
        return "forbidden", 403

    if data.get("type") == "confirmation":
        return VK_CONFIRMATION, 200

    if data.get("type") == "message_new":
        try:
            vk_session = vk_api.VkApi(token=VK_TOKEN)
            vk = vk_session.get_api()
            msg = data["object"]["message"]
            vk_id = msg["from_id"]
            text = msg.get("text", "")
            handle_message(vk, vk_id, text)
        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)

    return "ok", 200

# ─── ENTRY ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
