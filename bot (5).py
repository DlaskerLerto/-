import os
import random
import sqlite3
import logging
import json
import time
from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN", "")
VK_SECRET = os.environ.get("VK_SECRET", "")
VK_CONFIRMATION = os.environ.get("VK_CONFIRMATION", "")
DB_PATH = "game3.db"

# ─── ФРАКЦИИ ──────────────────────────────────────────────────────────────────

FACTIONS = {
    "Сталкеры":   {"desc": "Вольные бродяги Зоны.", "bonus": "+5 защиты, видят соседние сектора.", "start_tokens": 150, "start_warmth": 10, "attack_bonus": 0,   "defense_bonus": 5},
    "Долг":       {"desc": "Военизированная группировка.", "bonus": "+10 защиты, +5 атаки.",       "start_tokens": 120, "start_warmth": 15, "attack_bonus": 5,   "defense_bonus": 10},
    "Свобода":    {"desc": "Анархисты, быстрые и дерзкие.", "bonus": "+10 атаки, захват быстрее.", "start_tokens": 130, "start_warmth": 5,  "attack_bonus": 10,  "defense_bonus": 0},
    "Бандиты":    {"desc": "Мародёры. Богатеют за счёт других.", "bonus": "+30% жетонов с секторов, +15 атаки.", "start_tokens": 200, "start_warmth": 0, "attack_bonus": 15, "defense_bonus": -5},
    "Военные":    {"desc": "Армейские части. Тяжёлое снаряжение.", "bonus": "+15 защиты, +10 атаки.", "start_tokens": 100, "start_warmth": 20, "attack_bonus": 10, "defense_bonus": 15},
    "Монолит":    {"desc": "Фанатики Зоны. Не боятся аномалий.", "bonus": "Нет урона от аномалий. +20 атаки.", "start_tokens": 80,  "start_warmth": 30, "attack_bonus": 20, "defense_bonus": 10},
    "Наёмники":   {"desc": "Работают за деньги.", "bonus": "+250 стартовых жетонов, +10 атаки.", "start_tokens": 250, "start_warmth": 10, "attack_bonus": 10, "defense_bonus": 5},
    "Экологи":    {"desc": "Учёные Зоны. Знают артефакты.", "bonus": "x2 эффект артефактов.", "start_tokens": 120, "start_warmth": 15, "attack_bonus": -5, "defense_bonus": 5},
    "Ренегаты":   {"desc": "Дезертиры всех сторон.", "bonus": "+15 атаки, шанс диверсии.", "start_tokens": 140, "start_warmth": 5,  "attack_bonus": 15, "defense_bonus": -10},
    "Чистое Небо":{"desc": "Борцы с Зоной.", "bonus": "-50% урона от радиации. +5 атаки, +10 защиты.", "start_tokens": 130, "start_warmth": 20, "attack_bonus": 5, "defense_bonus": 10},
}

FACTION_RELATIONS = {
    "Сталкеры":    {"Долг": 20,  "Свобода": 40,  "Бандиты": -30, "Военные": -10, "Монолит": -50, "Наёмники": 0,   "Экологи": 30,  "Ренегаты": -40, "Чистое Небо": 20},
    "Долг":        {"Сталкеры": 20, "Свобода": -40, "Бандиты": -50, "Военные": 30, "Монолит": -60, "Наёмники": -10, "Экологи": 10, "Ренегаты": -50, "Чистое Небо": 30},
    "Свобода":     {"Сталкеры": 40, "Долг": -40,  "Бандиты": -20, "Военные": -30, "Монолит": -50, "Наёмники": 10,  "Экологи": 20,  "Ренегаты": -20, "Чистое Небо": 10},
    "Бандиты":     {"Сталкеры": -30,"Долг": -50,  "Свобода": -20, "Военные": -40, "Монолит": -30, "Наёмники": 20,  "Экологи": -20, "Ренегаты": 30,  "Чистое Небо": -30},
    "Военные":     {"Сталкеры": -10,"Долг": 30,   "Свобода": -30, "Бандиты": -40, "Монолит": -60, "Наёмники": -20, "Экологи": 20,  "Ренегаты": -50, "Чистое Небо": 20},
    "Монолит":     {"Сталкеры": -50,"Долг": -60,  "Свобода": -50, "Бандиты": -30, "Военные": -60, "Наёмники": -40, "Экологи": -30, "Ренегаты": -20, "Чистое Небо": -50},
    "Наёмники":    {"Сталкеры": 0,  "Долг": -10,  "Свобода": 10,  "Бандиты": 20,  "Военные": -20, "Монолит": -40,  "Экологи": 10,  "Ренегаты": 10,  "Чистое Небо": 0},
    "Экологи":     {"Сталкеры": 30, "Долг": 10,   "Свобода": 20,  "Бандиты": -20, "Военные": 20,  "Монолит": -30,  "Наёмники": 10, "Ренегаты": -30, "Чистое Небо": 30},
    "Ренегаты":    {"Сталкеры": -40,"Долг": -50,  "Свобода": -20, "Бандиты": 30,  "Военные": -50, "Монолит": -20,  "Наёмники": 10, "Экологи": -30,  "Чистое Небо": -20},
    "Чистое Небо": {"Сталкеры": 20, "Долг": 30,   "Свобода": 10,  "Бандиты": -30, "Военные": 20,  "Монолит": -50,  "Наёмники": 0,  "Экологи": 30,   "Ренегаты": -20},
}

# ─── СЕКТОРА ──────────────────────────────────────────────────────────────────

SECTORS = {
    1:  {"name": "Кордон",           "temp": -5,   "danger": 1, "tokens": 30,  "artifacts": 1},
    2:  {"name": "Свалка",           "temp": -12,  "danger": 1, "tokens": 35,  "artifacts": 1},
    3:  {"name": "Деревня новичков", "temp": -8,   "danger": 1, "tokens": 25,  "artifacts": 0},
    4:  {"name": "Агропром",         "temp": -18,  "danger": 2, "tokens": 50,  "artifacts": 2},
    5:  {"name": "Тёмная долина",    "temp": -22,  "danger": 2, "tokens": 55,  "artifacts": 2},
    6:  {"name": "Ржавые пустоши",   "temp": -28,  "danger": 2, "tokens": 60,  "artifacts": 2},
    7:  {"name": "Бар «100 рентген»","temp": -25,  "danger": 2, "tokens": 70,  "artifacts": 1},
    8:  {"name": "Мёртвый город",    "temp": -45,  "danger": 3, "tokens": 90,  "artifacts": 3},
    9:  {"name": "Радар",            "temp": -55,  "danger": 3, "tokens": 100, "artifacts": 3},
    10: {"name": "Янтарь",           "temp": -60,  "danger": 3, "tokens": 110, "artifacts": 4},
    11: {"name": "Туманный провал",  "temp": -75,  "danger": 4, "tokens": 140, "artifacts": 4},
    12: {"name": "Саркофаг",         "temp": -95,  "danger": 4, "tokens": 160, "artifacts": 5},
    13: {"name": "Припять",          "temp": -120, "danger": 5, "tokens": 200, "artifacts": 5},
    14: {"name": "ЧАЭС",             "temp": -155, "danger": 5, "tokens": 250, "artifacts": 6},
    15: {"name": "Ледяное сердце",   "temp": -200, "danger": 6, "tokens": 400, "artifacts": 8},
}

# ─── СНАРЯЖЕНИЕ ───────────────────────────────────────────────────────────────

WEAPONS = {
    "Кулаки":       {"attack": 0,   "cost": 0},
    "Нож":          {"attack": 5,   "cost": 20},
    "ПМ":           {"attack": 12,  "cost": 50},
    "АКС-74У":      {"attack": 25,  "cost": 150},
    "АК-74":        {"attack": 35,  "cost": 250},
    "СВД":          {"attack": 55,  "cost": 500},
    "РПГ-7":        {"attack": 80,  "cost": 900},
    "Гаусс-пушка":  {"attack": 130, "cost": 2000},
}

ARMORS = {
    "Нет":              {"defense": 0,  "warmth": 0,   "cost": 0},
    "Телогрейка":       {"defense": 3,  "warmth": 15,  "cost": 40},
    "Зимний костюм":    {"defense": 8,  "warmth": 30,  "cost": 120},
    "SEVA-костюм":      {"defense": 18, "warmth": 50,  "cost": 350},
    "Экзоскелет-С":     {"defense": 30, "warmth": 70,  "cost": 700},
    "Криокостюм Mk.I":  {"defense": 45, "warmth": 90,  "cost": 1400},
    "Криокостюм Mk.II": {"defense": 60, "warmth": 110, "cost": 2500},
    "Абсолют":          {"defense": 80, "warmth": 140, "cost": 5000},
}

ARTIFACTS = {
    "Медуза":       {"hp_bonus": 30,  "attack_bonus": 0,  "defense_bonus": 0,  "warmth_bonus": 0,  "cost": 80},
    "Огненный шар": {"hp_bonus": 0,   "attack_bonus": 15, "defense_bonus": 0,  "warmth_bonus": 5,  "cost": 120},
    "Кристалл":     {"hp_bonus": 0,   "attack_bonus": 0,  "defense_bonus": 10, "warmth_bonus": 10, "cost": 150},
    "Морской ёж":   {"hp_bonus": 50,  "attack_bonus": 10, "defense_bonus": 5,  "warmth_bonus": 0,  "cost": 200},
    "Пружина":      {"hp_bonus": 0,   "attack_bonus": 25, "defense_bonus": 0,  "warmth_bonus": 0,  "cost": 250},
    "Мамины бусы":  {"hp_bonus": 20,  "attack_bonus": 0,  "defense_bonus": 20, "warmth_bonus": 20, "cost": 400},
    "Душа":         {"hp_bonus": 100, "attack_bonus": 20, "defense_bonus": 20, "warmth_bonus": 30, "cost": 800},
}

ENEMIES = {
    1: [("Одичавшая собака", 25,  (4, 10),  8,   (5, 12)),
        ("Мародёр",          35,  (6, 13),  12,  (8, 20))],
    2: [("Зомби-солдат",     60,  (10, 18), 20,  (20, 40)),
        ("Кровосос",         80,  (14, 24), 30,  (30, 55))],
    3: [("Псевдогигант",     150, (22, 38), 50,  (60, 100)),
        ("Контролёр",        100, (18, 32), 40,  (50, 90))],
    4: [("Химера",           180, (30, 50), 70,  (90, 150)),
        ("Полтергейст",      120, (25, 45), 55,  (70, 120))],
    5: [("Страж Зоны",       280, (45, 70), 90,  (150, 250)),
        ("Излом",            220, (38, 62), 80,  (120, 200))],
    6: [("Вечный страж",     400, (65, 100),120, (250, 400)),
        ("Монолитовец",      300, (55, 85), 100, (200, 350))],
}

# ─── БД ───────────────────────────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        vk_id            INTEGER PRIMARY KEY,
        name             TEXT DEFAULT '__new__',
        state            TEXT DEFAULT 'start',
        faction          TEXT DEFAULT '',
        level            INTEGER DEFAULT 1,
        exp              INTEGER DEFAULT 0,
        tokens           INTEGER DEFAULT 0,
        hp               INTEGER DEFAULT 100,
        max_hp           INTEGER DEFAULT 100,
        attack           INTEGER DEFAULT 10,
        defense          INTEGER DEFAULT 0,
        warmth           INTEGER DEFAULT 0,
        weapon           TEXT DEFAULT 'Кулаки',
        armor            TEXT DEFAULT 'Нет',
        equipped_artifacts TEXT DEFAULT '[]',
        stored_artifacts TEXT DEFAULT '[]',
        controlled_sectors TEXT DEFAULT '[]',
        diplomacy        TEXT DEFAULT '{}',
        active_quest     TEXT DEFAULT '',
        quest_progress   INTEGER DEFAULT 0,
        completed_quests TEXT DEFAULT '[]',
        blowout_next     INTEGER DEFAULT 0,
        temp_selection   TEXT DEFAULT ''
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
    if not row:
        return None
    p = dict(row)
    for field in ("equipped_artifacts", "stored_artifacts", "controlled_sectors",
                  "diplomacy", "completed_quests"):
        p[field] = json.loads(p[field])
    return p

def save_player(p):
    data = dict(p)
    for field in ("equipped_artifacts", "stored_artifacts", "controlled_sectors",
                  "diplomacy", "completed_quests"):
        data[field] = json.dumps(p[field])
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    fields = [k for k in data if k != "vk_id"]
    sql = "UPDATE players SET " + ", ".join(f"{f}=?" for f in fields) + " WHERE vk_id=?"
    c.execute(sql, [data[f] for f in fields] + [p["vk_id"]])
    con.commit()
    con.close()

def create_player(vk_id):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO players (vk_id) VALUES (?)", (vk_id,))
    con.commit()
    con.close()

# ─── VK ───────────────────────────────────────────────────────────────────────

def send(vk, peer_id, text, keyboard=None):
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": get_random_id(),
    }
    if keyboard is not None:
        params["keyboard"] = json.dumps(keyboard)
    vk.messages.send(**params)

def kb(buttons, one_time=False):
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
    return {"one_time": one_time, "inline": False, "buttons": rows}

# ─── ХЕЛПЕРЫ ──────────────────────────────────────────────────────────────────

def calc_stats(p):
    f = FACTIONS.get(p["faction"], {})
    w = WEAPONS.get(p["weapon"], WEAPONS["Кулаки"])
    a = ARMORS.get(p["armor"], ARMORS["Нет"])
    attack = 10 + w["attack"] + f.get("attack_bonus", 0)
    defense = a["defense"] + f.get("defense_bonus", 0)
    warmth = a["warmth"] + f.get("start_warmth", 0)
    max_hp = 100
    for art_name in p["equipped_artifacts"]:
        art = ARTIFACTS.get(art_name, {})
        attack += art.get("attack_bonus", 0)
        defense += art.get("defense_bonus", 0)
        warmth += art.get("warmth_bonus", 0)
        max_hp += art.get("hp_bonus", 0)
        if p["faction"] == "Экологи":
            attack += art.get("attack_bonus", 0)
            defense += art.get("defense_bonus", 0)
            warmth += art.get("warmth_bonus", 0)
            max_hp += art.get("hp_bonus", 0)
    return {"attack": attack, "defense": defense, "warmth": warmth, "max_hp": max_hp}

def sector_min_warmth(sector_id):
    return max(0, -SECTORS[sector_id]["temp"] // 3)

def exp_for_next(level):
    return level * 150

def try_levelup(p):
    msgs = []
    while p["exp"] >= exp_for_next(p["level"]):
        p["exp"] -= exp_for_next(p["level"])
        p["level"] += 1
        p["max_hp"] += 20
        p["hp"] = p["max_hp"]
        msgs.append(f"⬆️ Уровень {p['level']}! +20 макс.HP")
    return msgs

def blowout_active(p):
    return int(time.time()) < p.get("blowout_next", 0)

# ─── ЭКРАНЫ ───────────────────────────────────────────────────────────────────

def screen_main(vk, p):
    stats = calc_stats(p)
    sectors_count = len(p["controlled_sectors"])
    blowout_warn = "\n⚡️ ВЫБРОС! Будь осторожен в секторах." if blowout_active(p) else ""
    text = (
        f"☢️ {p['name']} | {p['faction']} | Ур.{p['level']}\n"
        f"❤️ {p['hp']}/{p['max_hp']} | 💰 {p['tokens']} жетонов\n"
        f"⚔️ {stats['attack']} | 🛡 {stats['defense']} | 🌡 {stats['warmth']}\n"
        f"🗺 Секторов: {sectors_count}/15"
        f"{blowout_warn}"
    )
    keyboard = kb([
        [("🗺 Карта",       "primary"),    ("⚔️ В бой",     "negative")],
        [("🏪 Магазин",     "positive"),   ("🎒 Снаряжение","primary")],
        [("🤝 Дипломатия",  "secondary"),  ("📋 Квесты",    "secondary")],
        [("📊 Статус",      "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def screen_status(vk, p):
    stats = calc_stats(p)
    arts = ", ".join(p["equipped_artifacts"]) or "нет"
    text = (
        f"📊 ДОСЬЕ: {p['name']}\n"
        f"────────────────\n"
        f"Фракция: {p['faction']}\n"
        f"Уровень: {p['level']} | Опыт: {p['exp']}/{exp_for_next(p['level'])}\n"
        f"HP: {p['hp']}/{p['max_hp']}\n"
        f"Атака: {stats['attack']} | Защита: {stats['defense']}\n"
        f"Тепло: {stats['warmth']}\n"
        f"Жетоны: {p['tokens']}\n"
        f"Оружие: {p['weapon']}\n"
        f"Броня: {p['armor']}\n"
        f"Артефакты: {arts}\n"
        f"Секторов: {len(p['controlled_sectors'])}/15\n"
        f"Бонус: {FACTIONS[p['faction']]['bonus']}"
    )
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def screen_map(vk, p):
    stats = calc_stats(p)
    text = "🗺 КАРТА ЗОНЫ\n────────────────\n"
    for sid, s in SECTORS.items():
        owned = "🟢" if sid in p["controlled_sectors"] else "⬜"
        needed = sector_min_warmth(sid)
        lock = ""
        if p["level"] < s["danger"]:
            lock = f" 🔒{s['danger']}ур"
        elif needed > stats["warmth"]:
            lock = f" 🥶{needed}"
        text += f"{owned} {s['name']} | {s['temp']}°C | {'☠'*s['danger']}{lock}\n"
    btns = []
    row = []
    for sid, s in SECTORS.items():
        label = f"{'✅' if sid in p['controlled_sectors'] else '⚔️'} {s['name']}"
        color = "positive" if sid in p["controlled_sectors"] else "negative"
        row.append((label[:40], color))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_equipment(vk, p):
    stats = calc_stats(p)
    stored = {}
    for a in p["stored_artifacts"]:
        stored[a] = stored.get(a, 0) + 1
    arts_equipped = ", ".join(p["equipped_artifacts"]) or "нет"
    arts_stored = ", ".join(f"{k} x{v}" for k, v in stored.items()) or "нет"
    text = (
        f"🎒 СНАРЯЖЕНИЕ\n"
        f"────────────────\n"
        f"🔫 Оружие: {p['weapon']} (+{WEAPONS[p['weapon']]['attack']}⚔️)\n"
        f"🥼 Броня: {p['armor']} (+{ARMORS[p['armor']]['warmth']}🌡 +{ARMORS[p['armor']]['defense']}🛡)\n"
        f"💎 Надето: {arts_equipped}\n"
        f"📦 Склад: {arts_stored}\n"
        f"────────────────\n"
        f"⚔️ {stats['attack']} | 🛡 {stats['defense']} | 🌡 {stats['warmth']} | ❤️ {stats['max_hp']}"
    )
    btns = [
        [("🔫 Сменить оружие", "primary"),  ("🥼 Сменить броню", "primary")],
        [("💎 Надеть артефакт", "secondary"),("💎 Снять артефакт", "secondary")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_shop(vk, p):
    text = f"🏪 МАГАЗИН\nЖетоны: {p['tokens']}\n────────────────\n"
    text += "ОРУЖИЕ:\n"
    for name, w in WEAPONS.items():
        if w["cost"] > 0:
            mark = "✅ " if p["weapon"] == name else ""
            text += f"{mark}• {name}: {w['cost']}жт | +{w['attack']}⚔️\n"
    text += "\nБРОНЯ:\n"
    for name, a in ARMORS.items():
        if a["cost"] > 0:
            mark = "✅ " if p["armor"] == name else ""
            text += f"{mark}• {name}: {a['cost']}жт | +{a['defense']}🛡 +{a['warmth']}🌡\n"
    text += "\nАРТЕФАКТЫ:\n"
    for name, art in ARTIFACTS.items():
        text += f"• {name}: {art['cost']}жт | ❤️+{art['hp_bonus']} ⚔️+{art['attack_bonus']} 🛡+{art['defense_bonus']} 🌡+{art['warmth_bonus']}\n"
    btns = [
        [("Купить оружие", "primary"),    ("Купить броню",     "primary")],
        [("Купить артефакт", "positive")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_buy_weapon(vk, p):
    text = f"🔫 ВЫБОР ОРУЖИЯ\nЖетоны: {p['tokens']}\n────────────────\n"
    btns = []
    for name, w in WEAPONS.items():
        if w["cost"] == 0:
            continue
        can = p["tokens"] >= w["cost"]
        mark = "✅ " if p["weapon"] == name else ("" if can else "❌ ")
        label = f"{mark}{name} ({w['cost']}жт, +{w['attack']}⚔️)"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))
    p["temp_selection"] = "buy_weapon"
    save_player(p)

def screen_buy_armor(vk, p):
    text = f"🥼 ВЫБОР БРОНИ\nЖетоны: {p['tokens']}\n────────────────\n"
    btns = []
    for name, a in ARMORS.items():
        if a["cost"] == 0:
            continue
        can = p["tokens"] >= a["cost"]
        mark = "✅ " if p["armor"] == name else ("" if can else "❌ ")
        label = f"{mark}{name} ({a['cost']}жт, +{a['warmth']}🌡)"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))
    p["temp_selection"] = "buy_armor"
    save_player(p)

def screen_buy_artifact(vk, p):
    text = f"💎 КУПИТЬ АРТЕФАКТ\nЖетоны: {p['tokens']}\n────────────────\n"
    btns = []
    for name, art in ARTIFACTS.items():
        can = p["tokens"] >= art["cost"]
        label = f"{'❌ ' if not can else ''}{name} ({art['cost']}жт)"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))
    p["temp_selection"] = "buy_artifact"
    save_player(p)

def screen_equip_artifact(vk, p):
    if not p["stored_artifacts"]:
        send(vk, p["vk_id"], "Нет артефактов на складе.", None)
        screen_equipment(vk, p)
        return
    text = "💎 НАДЕТЬ АРТЕФАКТ\n────────────────\n"
    btns = []
    seen = []
    for name in p["stored_artifacts"]:
        if name not in seen:
            seen.append(name)
            art = ARTIFACTS[name]
            label = f"Надеть: {name}"
            btns.append([(label[:40], "positive")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))
    p["temp_selection"] = "equip_artifact"
    save_player(p)

def screen_unequip_artifact(vk, p):
    if not p["equipped_artifacts"]:
        send(vk, p["vk_id"], "Нет надетых артефактов.", None)
        screen_equipment(vk, p)
        return
    text = "💎 СНЯТЬ АРТЕФАКТ\n────────────────\n"
    btns = []
    for name in p["equipped_artifacts"]:
        btns.append([(f"Снять: {name}"[:40], "negative")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))
    p["temp_selection"] = "unequip_artifact"
    save_player(p)

def screen_diplomacy(vk, p):
    text = f"🤝 ДИПЛОМАТИЯ — {p['faction']}\n────────────────\n"
    for fname, rel in p["diplomacy"].items():
        if rel >= 50:
            status = "🟢 Союзник"
        elif rel >= 10:
            status = "🔵 Нейтрал"
        elif rel >= -20:
            status = "🟡 Напряжённо"
        else:
            status = "🔴 Война"
        text += f"{fname}: {status} ({rel})\n"
    btns = [
        [("Объявить союз", "positive"), ("Объявить войну", "negative")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_quests(vk, p):
    text = "📋 КВЕСТЫ\n────────────────\n"
    if p["active_quest"]:
        text += f"▶️ Активный: {p['active_quest']}\nПрогресс: {p['quest_progress']}\n────────────────\n"
    text += f"✅ Выполнено: {len(p['completed_quests'])}\n\nЗадания появляются при захвате секторов."
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def screen_choose_faction(vk, p):
    send(vk, p["vk_id"], "☢️ ВЫБЕРИ ФРАКЦИЮ\n────────────────\nНажми на название чтобы узнать подробнее:",
         kb([[name] for name in FACTIONS]))

def screen_faction_info(vk, p, fname):
    f = FACTIONS[fname]
    text = (
        f"☢️ {fname}\n────────────────\n"
        f"{f['desc']}\n\n"
        f"Бонус: {f['bonus']}\n"
        f"Стартовые жетоны: {f['start_tokens']}\n"
        f"Стартовое тепло: +{f['start_warmth']}"
    )
    p["temp_selection"] = f"pending_faction:{fname}"
    save_player(p)
    send(vk, p["vk_id"], text, kb([
        [(f"✅ Выбрать {fname}"[:40], "positive")],
        [("◀️ Другая фракция", "secondary")],
    ]))

# ─── БОЙ ──────────────────────────────────────────────────────────────────────

def do_battle(vk, p, sector_id):
    s = SECTORS[sector_id]
    stats = calc_stats(p)

    needed_warmth = sector_min_warmth(sector_id)
    temp_penalty = max(0, needed_warmth - stats["warmth"])
    eff_attack = max(1, stats["attack"] - temp_penalty // 2)
    eff_defense = max(0, stats["defense"] - temp_penalty)

    danger = min(s["danger"], 6)
    enemy_pool = ENEMIES[danger]
    enemy_name, enemy_hp, enemy_dmg_range, enemy_exp, enemy_tokens_range = random.choice(enemy_pool)

    player_hp = p["hp"]
    log = []
    for _ in range(6):
        if player_hp <= 0 or enemy_hp <= 0:
            break
        p_dmg = max(1, eff_attack + random.randint(-3, 5))
        e_dmg = max(0, random.randint(*enemy_dmg_range) - eff_defense)
        enemy_hp -= p_dmg
        player_hp -= e_dmg
        log.append(f"⚔️ {p_dmg} урона → враг получил {e_dmg}")

    result = f"⚔️ {s['name']} | {s['temp']}°C\nПротивник: {enemy_name}\n────────────────\n"
    result += "\n".join(log[:3]) + "\n────────────────\n"

    if temp_penalty > 0:
        result += f"🥶 Штраф холода: -{temp_penalty} к защите\n"

    if enemy_hp <= 0:
        tokens_gain = random.randint(*enemy_tokens_range)
        if p["faction"] == "Бандиты":
            tokens_gain = int(tokens_gain * 1.3)
        exp_gain = enemy_exp
        arts_found = []
        for _ in range(s["artifacts"]):
            if random.random() < 0.3:
                arts_found.append(random.choice(list(ARTIFACTS.keys())))

        p["tokens"] += tokens_gain
        p["exp"] += exp_gain
        p["hp"] = max(1, player_hp)
        if arts_found:
            p["stored_artifacts"].extend(arts_found)
        if sector_id not in p["controlled_sectors"]:
            p["controlled_sectors"].append(sector_id)

        # Выброс
        if blowout_active(p) and p["faction"] != "Монолит":
            dmg = s["danger"] * 8
            p["tokens"] = max(0, p["tokens"] - dmg)
            result += f"⚡️ Выброс: -{dmg} жетонов!\n"

        lu = try_levelup(p)
        result += f"✅ ПОБЕДА!\n+{tokens_gain} жетонов | +{exp_gain} опыта\n"
        if arts_found:
            result += f"💎 Найдено: {', '.join(arts_found)}\n"
        for m in lu:
            result += f"{m}\n"
        if len(p["controlled_sectors"]) >= 15:
            result += "\n🏆 ТЫ ЗАХВАТИЛ ВСЮ ЗОНУ! Победа!"
    else:
        penalty = int(p["tokens"] * 0.1)
        p["tokens"] = max(0, p["tokens"] - penalty)
        p["hp"] = max(1, player_hp)
        result += f"💔 ПОРАЖЕНИЕ. -{penalty} жетонов. HP: {p['hp']}\n"

    # Следующий выброс
    if random.random() < 0.15:
        p["blowout_next"] = int(time.time()) + random.randint(300, 900)
        result += "\n⚡️ Приближается выброс!"

    save_player(p)
    send(vk, p["vk_id"], result, kb([
        [("⚔️ Ещё раз", "negative"), ("◀️ В лагерь", "secondary")]
    ]))

# ─── ОБРАБОТЧИК ───────────────────────────────────────────────────────────────

def handle_message(vk, vk_id, text):
    text = text.strip()
    p = get_player(vk_id)

    if not p:
        create_player(vk_id)
        send(vk, vk_id,
             "❄️ ЗОНА. ЯДЕРНАЯ ЗИМА.\n────────────────\n"
             "Температура в эпицентре: -200°C.\n"
             "Ты один против всей Зоны.\n\n"
             "Введи своё имя, сталкер:",
             kb([[("Начать", "positive")]]))
        return

    state = p["state"]

    # ── Ввод имени ──
    if state == "start":
        if text == "Начать":
            send(vk, vk_id, "Введи своё имя:", None)
            return
        if len(text.strip()) < 2:
            send(vk, vk_id, "Имя слишком короткое.", None)
            return
        p["name"] = text[:20].strip()
        p["state"] = "choose_faction"
        save_player(p)
        screen_choose_faction(vk, p)
        return

    # ── Выбор фракции ──
    if state == "choose_faction":
        if text in FACTIONS:
            screen_faction_info(vk, p, text)
            return
        if text.startswith("✅ Выбрать "):
            fname = text[10:].strip()
            if fname not in FACTIONS:
                fname = p["temp_selection"].replace("pending_faction:", "") if p["temp_selection"].startswith("pending_faction:") else ""
            if fname in FACTIONS:
                f = FACTIONS[fname]
                p["faction"] = fname
                p["tokens"] = f["start_tokens"]
                p["warmth"] = f["start_warmth"]
                p["controlled_sectors"] = [1]
                p["diplomacy"] = {k: v for k, v in FACTION_RELATIONS[fname].items()}
                p["state"] = "main"
                p["blowout_next"] = int(time.time()) + 900
                save_player(p)
                send(vk, vk_id,
                     f"✅ Фракция: {fname}\n"
                     f"База: Кордон (-5°C)\n"
                     f"Жетоны: {f['start_tokens']}\n"
                     f"Захвати все 15 секторов!", None)
                screen_main(vk, p)
                return
        if text == "◀️ Другая фракция":
            screen_choose_faction(vk, p)
            return
        screen_choose_faction(vk, p)
        return

    # ── Навигация ──
    if text in ("◀️ Назад", "◀️ В лагерь"):
        p["temp_selection"] = ""
        save_player(p)
        screen_main(vk, p)
        return

    if text == "🗺 Карта":        screen_map(vk, p); return
    if text == "📊 Статус":       screen_status(vk, p); return
    if text == "🏪 Магазин":      screen_shop(vk, p); return
    if text == "🎒 Снаряжение":   screen_equipment(vk, p); return
    if text == "🤝 Дипломатия":   screen_diplomacy(vk, p); return
    if text == "📋 Квесты":       screen_quests(vk, p); return
    if text == "Купить оружие":   screen_buy_weapon(vk, p); return
    if text == "Купить броню":    screen_buy_armor(vk, p); return
    if text == "Купить артефакт": screen_buy_artifact(vk, p); return
    if text == "🔫 Сменить оружие": screen_buy_weapon(vk, p); return
    if text == "🥼 Сменить броню":  screen_buy_armor(vk, p); return
    if text == "💎 Надеть артефакт": screen_equip_artifact(vk, p); return
    if text == "💎 Снять артефакт":  screen_unequip_artifact(vk, p); return

    # ── Бой ──
    if text in ("⚔️ В бой", "⚔️ Ещё раз"):
        uncaptured = [sid for sid in SECTORS if sid not in p["controlled_sectors"]]
        if not uncaptured:
            send(vk, vk_id, "🏆 Все сектора захвачены! Ты победил!", None)
            return
        stats = calc_stats(p)
        # Выбираем доступный сектор с наименьшим id
        available = [sid for sid in uncaptured
                     if p["level"] >= SECTORS[sid]["danger"]
                     and stats["warmth"] >= sector_min_warmth(sid)]
        if not available:
            available = uncaptured
        target = min(available)
        do_battle(vk, p, target)
        return

    # Атака с карты
    for sid, s in SECTORS.items():
        if f"⚔️ {s['name']}" in text or f"✅ {s['name']}" in text:
            stats = calc_stats(p)
            if p["level"] < s["danger"]:
                send(vk, vk_id, f"🔒 Нужен {s['danger']} уровень.", None)
                screen_map(vk, p)
                return
            needed = sector_min_warmth(sid)
            if needed > stats["warmth"]:
                send(vk, vk_id, f"🥶 Нужно тепло {needed}. Купи броню.", None)
                screen_map(vk, p)
                return
            do_battle(vk, p, sid)
            return

    # ── Покупка оружия ──
    if p["temp_selection"] == "buy_weapon":
        for name, w in WEAPONS.items():
            if name in text and w["cost"] > 0:
                if p["tokens"] < w["cost"]:
                    send(vk, vk_id, f"Не хватает жетонов. Нужно {w['cost']}.", None)
                    screen_buy_weapon(vk, p)
                    return
                p["tokens"] -= w["cost"]
                p["weapon"] = name
                p["temp_selection"] = ""
                save_player(p)
                send(vk, vk_id, f"✅ Оружие: {name}. Атака +{w['attack']}.", None)
                screen_equipment(vk, p)
                return

    # ── Покупка брони ──
    if p["temp_selection"] == "buy_armor":
        for name, a in ARMORS.items():
            if name in text and a["cost"] > 0:
                if p["tokens"] < a["cost"]:
                    send(vk, vk_id, f"Не хватает жетонов. Нужно {a['cost']}.", None)
                    screen_buy_armor(vk, p)
                    return
                p["tokens"] -= a["cost"]
                p["armor"] = name
                p["temp_selection"] = ""
                save_player(p)
                send(vk, vk_id, f"✅ Броня: {name}. Тепло +{a['warmth']}, Защита +{a['defense']}.", None)
                screen_equipment(vk, p)
                return

    # ── Покупка артефакта ──
    if p["temp_selection"] == "buy_artifact":
        for name, art in ARTIFACTS.items():
            if name in text:
                if p["tokens"] < art["cost"]:
                    send(vk, vk_id, f"Не хватает жетонов. Нужно {art['cost']}.", None)
                    screen_buy_artifact(vk, p)
                    return
                p["tokens"] -= art["cost"]
                p["stored_artifacts"].append(name)
                p["temp_selection"] = ""
                save_player(p)
                send(vk, vk_id, f"✅ Артефакт куплен: {name}. Лежит на складе.", None)
                screen_equipment(vk, p)
                return

    # ── Надеть артефакт ──
    if p["temp_selection"] == "equip_artifact" and text.startswith("Надеть: "):
        art_name = text[8:]
        if art_name in p["stored_artifacts"]:
            p["stored_artifacts"].remove(art_name)
            p["equipped_artifacts"].append(art_name)
            p["temp_selection"] = ""
            save_player(p)
            send(vk, vk_id, f"✅ {art_name} надет.", None)
            screen_equipment(vk, p)
            return

    # ── Снять артефакт ──
    if p["temp_selection"] == "unequip_artifact" and text.startswith("Снять: "):
        art_name = text[7:]
        if art_name in p["equipped_artifacts"]:
            p["equipped_artifacts"].remove(art_name)
            p["stored_artifacts"].append(art_name)
            p["temp_selection"] = ""
            save_player(p)
            send(vk, vk_id, f"✅ {art_name} снят, лежит на складе.", None)
            screen_equipment(vk, p)
            return

    # ── Дипломатия ──
    if text == "Объявить союз":
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_selection"] = "diplo_ally"
        save_player(p)
        send(vk, p["vk_id"], "🤝 С кем заключить союз?", kb(btns))
        return

    if text == "Объявить войну":
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_selection"] = "diplo_war"
        save_player(p)
        send(vk, p["vk_id"], "⚔️ На кого объявить войну?", kb(btns))
        return

    if p["temp_selection"] == "diplo_ally" and text in FACTIONS:
        p["diplomacy"][text] = min(100, p["diplomacy"].get(text, 0) + 40)
        p["temp_selection"] = ""
        save_player(p)
        send(vk, vk_id, f"🤝 Союз с {text}. Отношения: {p['diplomacy'][text]}.", None)
        screen_main(vk, p)
        return

    if p["temp_selection"] == "diplo_war" and text in FACTIONS:
        p["diplomacy"][text] = max(-100, p["diplomacy"].get(text, 0) - 60)
        p["temp_selection"] = ""
        save_player(p)
        send(vk, vk_id, f"⚔️ Война с {text}. Отношения: {p['diplomacy'][text]}.", None)
        screen_main(vk, p)
        return

    # Fallback
    screen_main(vk, p)

# ─── WEBHOOK ──────────────────────────────────────────────────────────────────

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

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
