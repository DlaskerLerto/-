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
DB_PATH = "game2.db"

# ─── ФРАКЦИИ ──────────────────────────────────────────────────────────────────

FACTIONS = {
    "Сталкеры": {
        "desc": "Вольные бродяги. Знают Зону как никто.",
        "bonus": "Разведка: видят соседние сектора без вылазки.",
        "start_tokens": 150,
        "start_warmth": 10,
        "attack_bonus": 0,
        "defense_bonus": 5,
        "relations": {"Долг": 20, "Свобода": 40, "Бандиты": -30, "Военные": -10,
                      "Монолит": -50, "Наёмники": 0, "Экологи": 30,
                      "Ренегаты": -40, "Чистое Небо": 20, "О-Сознание": -20},
    },
    "Долг": {
        "desc": "Военизированная группировка. Дисциплина и огневая мощь.",
        "bonus": "Броня: все отряды получают +10 к защите.",
        "start_tokens": 120,
        "start_warmth": 15,
        "attack_bonus": 5,
        "defense_bonus": 10,
        "relations": {"Сталкеры": 20, "Свобода": -40, "Бандиты": -50, "Военные": 30,
                      "Монолит": -60, "Наёмники": -10, "Экологи": 10,
                      "Ренегаты": -50, "Чистое Небо": 30, "О-Сознание": -30},
    },
    "Свобода": {
        "desc": "Анархисты. Быстро передвигаются, живут вольно.",
        "bonus": "Скорость: захват секторов на 20% быстрее.",
        "start_tokens": 130,
        "start_warmth": 5,
        "attack_bonus": 10,
        "defense_bonus": 0,
        "relations": {"Сталкеры": 40, "Долг": -40, "Бандиты": -20, "Военные": -30,
                      "Монолит": -50, "Наёмники": 10, "Экологи": 20,
                      "Ренегаты": -20, "Чистое Небо": 10, "О-Сознание": -10},
    },
    "Бандиты": {
        "desc": "Мародёры и головорезы. Богатеют за счёт других.",
        "bonus": "Грабёж: +30% жетонов с каждого захваченного сектора.",
        "start_tokens": 200,
        "start_warmth": 0,
        "attack_bonus": 15,
        "defense_bonus": -5,
        "relations": {"Сталкеры": -30, "Долг": -50, "Свобода": -20, "Военные": -40,
                      "Монолит": -30, "Наёмники": 20, "Экологи": -20,
                      "Ренегаты": 30, "Чистое Небо": -30, "О-Сознание": -10},
    },
    "Военные": {
        "desc": "Армейские части. Тяжёлое снаряжение, строгий устав.",
        "bonus": "Снабжение: можно нанимать элитных бойцов сразу.",
        "start_tokens": 100,
        "start_warmth": 20,
        "attack_bonus": 10,
        "defense_bonus": 15,
        "relations": {"Сталкеры": -10, "Долг": 30, "Свобода": -30, "Бандиты": -40,
                      "Монолит": -60, "Наёмники": -20, "Экологи": 20,
                      "Ренегаты": -50, "Чистое Небо": 20, "О-Сознание": -40},
    },
    "Монолит": {
        "desc": "Фанатики Зоны. Безумны, но непобедимы вблизи центра.",
        "bonus": "Адаптация: не получают урон от аномалий в глубоких зонах.",
        "start_tokens": 80,
        "start_warmth": 30,
        "attack_bonus": 20,
        "defense_bonus": 10,
        "relations": {"Сталкеры": -50, "Долг": -60, "Свобода": -50, "Бандиты": -30,
                      "Военные": -60, "Наёмники": -40, "Экологи": -30,
                      "Ренегаты": -20, "Чистое Небо": -50, "О-Сознание": 50},
    },
    "Наёмники": {
        "desc": "Работают за деньги. Нейтральны, но продажны.",
        "bonus": "Контракты: могут временно нанимать бойцов других фракций.",
        "start_tokens": 250,
        "start_warmth": 10,
        "attack_bonus": 10,
        "defense_bonus": 5,
        "relations": {"Сталкеры": 0, "Долг": -10, "Свобода": 10, "Бандиты": 20,
                      "Военные": -20, "Монолит": -40, "Экологи": 10,
                      "Ренегаты": 10, "Чистое Небо": 0, "О-Сознание": -10},
    },
    "Экологи": {
        "desc": "Учёные Зоны. Слабы в бою, но лучшие знатоки артефактов.",
        "bonus": "Артефакты: получают двойной эффект от артефактов.",
        "start_tokens": 120,
        "start_warmth": 15,
        "attack_bonus": -5,
        "defense_bonus": 5,
        "relations": {"Сталкеры": 30, "Долг": 10, "Свобода": 20, "Бандиты": -20,
                      "Военные": 20, "Монолит": -30, "Наёмники": 10,
                      "Ренегаты": -30, "Чистое Небо": 30, "О-Сознание": 20},
    },
    "Ренегаты": {
        "desc": "Дезертиры и предатели. Знают тактику всех сторон.",
        "bonus": "Диверсия: шанс ослабить вражеский отряд перед атакой.",
        "start_tokens": 140,
        "start_warmth": 5,
        "attack_bonus": 15,
        "defense_bonus": -10,
        "relations": {"Сталкеры": -40, "Долг": -50, "Свобода": -20, "Бандиты": 30,
                      "Военные": -50, "Монолит": -20, "Наёмники": 10,
                      "Экологи": -30, "Чистое Небо": -20, "О-Сознание": -10},
    },
    "Чистое Небо": {
        "desc": "Борцы с Зоной. Хотят уничтожить аномалии навсегда.",
        "bonus": "Очищение: уменьшают радиационный урон для всех отрядов.",
        "start_tokens": 130,
        "start_warmth": 20,
        "attack_bonus": 5,
        "defense_bonus": 10,
        "relations": {"Сталкеры": 20, "Долг": 30, "Свобода": 10, "Бандиты": -30,
                      "Военные": 20, "Монолит": -50, "Наёмники": 0,
                      "Экологи": 30, "Ренегаты": -20, "О-Сознание": -40},
    },
}

# ─── СЕКТОРА КАРТЫ ────────────────────────────────────────────────────────────

SECTORS = {
    1:  {"name": "Кордон",          "temp": -5,   "danger": 1, "ring": 1, "tokens": 30,  "artifacts": 1},
    2:  {"name": "Свалка",          "temp": -12,  "danger": 1, "ring": 1, "tokens": 35,  "artifacts": 1},
    3:  {"name": "Деревня новичков","temp": -8,   "danger": 1, "ring": 1, "tokens": 25,  "artifacts": 0},
    4:  {"name": "Агропром",        "temp": -18,  "danger": 2, "ring": 2, "tokens": 50,  "artifacts": 2},
    5:  {"name": "Тёмная долина",   "temp": -22,  "danger": 2, "ring": 2, "tokens": 55,  "artifacts": 2},
    6:  {"name": "Ржавые пустоши",  "temp": -28,  "danger": 2, "ring": 2, "tokens": 60,  "artifacts": 2},
    7:  {"name": "Бар «100 рентген»","temp": -25, "danger": 2, "ring": 2, "tokens": 70,  "artifacts": 1},
    8:  {"name": "Мёртвый город",   "temp": -45,  "danger": 3, "ring": 3, "tokens": 90,  "artifacts": 3},
    9:  {"name": "Радар",           "temp": -55,  "danger": 3, "ring": 3, "tokens": 100, "artifacts": 3},
    10: {"name": "Янтарь",          "temp": -60,  "danger": 3, "ring": 3, "tokens": 110, "artifacts": 4},
    11: {"name": "Туманный провал", "temp": -75,  "danger": 4, "ring": 4, "tokens": 140, "artifacts": 4},
    12: {"name": "Саркофаг",        "temp": -95,  "danger": 4, "ring": 4, "tokens": 160, "artifacts": 5},
    13: {"name": "Припять",         "temp": -120, "danger": 5, "ring": 5, "tokens": 200, "artifacts": 5},
    14: {"name": "ЧАЭС",            "temp": -155, "danger": 5, "ring": 5, "tokens": 250, "artifacts": 6},
    15: {"name": "Ледяное сердце",  "temp": -200, "danger": 6, "ring": 6, "tokens": 400, "artifacts": 8},
}

# Соседние сектора (для движения)
SECTOR_NEIGHBORS = {
    1: [2, 3], 2: [1, 3, 4], 3: [1, 2, 5],
    4: [2, 5, 6, 7], 5: [3, 4, 6], 6: [4, 5, 7, 8],
    7: [4, 6, 8, 9], 8: [6, 7, 9, 10], 9: [7, 8, 10, 11],
    10: [8, 9, 11, 12], 11: [9, 10, 12, 13], 12: [10, 11, 13, 14],
    13: [11, 12, 14, 15], 14: [12, 13, 15], 15: [13, 14],
}

# ─── ЮНИТЫ И СНАРЯЖЕНИЕ ───────────────────────────────────────────────────────

UNIT_TYPES = {
    "Новобранец":   {"hp": 50,  "attack": 8,  "defense": 3,  "cost": 40,  "warmth_req": 0,   "level_req": 1},
    "Боец":         {"hp": 80,  "attack": 14, "defense": 6,  "cost": 100, "warmth_req": 10,  "level_req": 2},
    "Ветеран":      {"hp": 120, "attack": 22, "defense": 12, "cost": 250, "warmth_req": 25,  "level_req": 4},
    "Элитный":      {"hp": 180, "attack": 35, "defense": 20, "cost": 500, "warmth_req": 40,  "level_req": 6},
    "Призрак":      {"hp": 250, "attack": 55, "defense": 30, "cost": 1000,"warmth_req": 60,  "level_req": 9},
}

WEAPONS = {
    "Кулаки":        {"attack": 0,   "cost": 0,    "warmth": 0},
    "Нож":           {"attack": 5,   "cost": 20,   "warmth": 0},
    "ПМ":            {"attack": 12,  "cost": 50,   "warmth": 0},
    "АКС-74У":       {"attack": 25,  "cost": 150,  "warmth": 0},
    "АК-74":         {"attack": 35,  "cost": 250,  "warmth": 0},
    "СВД":           {"attack": 55,  "cost": 500,  "warmth": 0},
    "РПГ-7":         {"attack": 80,  "cost": 900,  "warmth": 0},
    "Гаусс-пушка":   {"attack": 130, "cost": 2000, "warmth": 0},
}

ARMORS = {
    "Нет":             {"defense": 0,  "warmth": 0,  "cost": 0},
    "Телогрейка":      {"defense": 3,  "warmth": 15, "cost": 40},
    "Зимний костюм":   {"defense": 8,  "warmth": 30, "cost": 120},
    "SEVA-костюм":     {"defense": 18, "warmth": 50, "cost": 350},
    "Экзоскелет-С":    {"defense": 30, "warmth": 70, "cost": 700},
    "Криокостюм Mk.I": {"defense": 45, "warmth": 90, "cost": 1400},
    "Криокостюм Mk.II":{"defense": 60, "warmth": 110,"cost": 2500},
    "Абсолют":         {"defense": 80, "warmth": 140,"cost": 5000},
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
    1: [("Одичавшая собака", 25, (4,10), 8, (5,12)),
        ("Мародёр",          35, (6,13), 12,(8,20))],
    2: [("Зомби-солдат",     60, (10,18),20,(20,40)),
        ("Кровосос",         80, (14,24),30,(30,55))],
    3: [("Псевдогигант",    150, (22,38),50,(60,100)),
        ("Контролёр",       100, (18,32),40,(50,90))],
    4: [("Химера",          180, (30,50),70,(90,150)),
        ("Полтергейст",     120, (25,45),55,(70,120))],
    5: [("Страж Зоны",      280, (45,70),90,(150,250)),
        ("Излом",           220, (38,62),80,(120,200))],
    6: [("Вечный страж",    400, (65,100),120,(250,400)),
        ("Монолитовец",     300, (55,85), 100,(200,350))],
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
        warmth           INTEGER DEFAULT 0,
        home_sector      INTEGER DEFAULT 1,
        controlled_sectors TEXT DEFAULT '[]',
        squads           TEXT DEFAULT '[]',
        artifacts        TEXT DEFAULT '[]',
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
    p["controlled_sectors"] = json.loads(p["controlled_sectors"])
    p["squads"] = json.loads(p["squads"])
    p["artifacts"] = json.loads(p["artifacts"])
    p["diplomacy"] = json.loads(p["diplomacy"])
    p["completed_quests"] = json.loads(p["completed_quests"])
    return p

def save_player(p):
    data = dict(p)
    data["controlled_sectors"] = json.dumps(p["controlled_sectors"])
    data["squads"] = json.dumps(p["squads"])
    data["artifacts"] = json.dumps(p["artifacts"])
    data["diplomacy"] = json.dumps(p["diplomacy"])
    data["completed_quests"] = json.dumps(p["completed_quests"])
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

# ─── ИГРОВЫЕ ХЕЛПЕРЫ ──────────────────────────────────────────────────────────

def squad_power(squad, faction_name):
    f = FACTIONS[faction_name]
    w = WEAPONS.get(squad.get("weapon", "Кулаки"), WEAPONS["Кулаки"])
    a = ARMORS.get(squad.get("armor", "Нет"), ARMORS["Нет"])
    base_unit = UNIT_TYPES.get(squad.get("unit_type", "Новобранец"), UNIT_TYPES["Новобранец"])
    attack = base_unit["attack"] + w["attack"] + f["attack_bonus"]
    defense = base_unit["defense"] + a["defense"] + f["defense_bonus"]
    hp = base_unit["hp"]
    warmth = a["warmth"] + f["start_warmth"]
    for art_name in squad.get("artifacts", []):
        art = ARTIFACTS.get(art_name, {})
        attack += art.get("attack_bonus", 0)
        defense += art.get("defense_bonus", 0)
        hp += art.get("hp_bonus", 0)
        warmth += art.get("warmth_bonus", 0)
    return {"attack": attack, "defense": defense, "hp": hp, "warmth": warmth}

def sector_min_warmth(sector_id):
    s = SECTORS[sector_id]
    return max(0, -s["temp"] // 3)

def can_enter_sector(squad, sector_id, faction_name):
    power = squad_power(squad, faction_name)
    needed = sector_min_warmth(sector_id)
    return power["warmth"] >= needed

def new_squad(unit_type="Новобранец"):
    return {
        "id": random.randint(10000, 99999),
        "unit_type": unit_type,
        "count": random.randint(2, 4),
        "weapon": "Кулаки",
        "armor": "Нет",
        "artifacts": [],
        "sector": None,
        "alive": True,
    }

def blowout_active(p):
    return int(time.time()) < p.get("blowout_next", 0)

def schedule_blowout(p):
    p["blowout_next"] = int(time.time()) + random.randint(600, 1800)

def exp_for_next(level):
    return level * 150

def try_levelup(p):
    msgs = []
    while p["exp"] >= exp_for_next(p["level"]):
        p["exp"] -= exp_for_next(p["level"])
        p["level"] += 1
        msgs.append(f"⬆️ Уровень {p['level']}! Доступны новые юниты и секторы.")
    return msgs

# ─── ЭКРАНЫ ───────────────────────────────────────────────────────────────────

def screen_main(vk, p):
    f = FACTIONS[p["faction"]]
    sectors_count = len(p["controlled_sectors"])
    squads_alive = [s for s in p["squads"] if s["alive"]]
    blowout_warn = "\n⚡️ ВЫБРОС АКТИВЕН! Отряды в открытых секторах под угрозой." if blowout_active(p) else ""
    text = (
        f"☢️ {p['name']} | {p['faction']} | Ур.{p['level']}\n"
        f"💰 {p['tokens']} жетонов | 🌡 Тепло: {p['warmth']}\n"
        f"🗺 Секторов: {sectors_count}/15 | 👥 Отрядов: {len(squads_alive)}\n"
        f"📍 База: {SECTORS[p['home_sector']]['name']} ({SECTORS[p['home_sector']]['temp']}°C)"
        f"{blowout_warn}"
    )
    keyboard = kb([
        [("🗺 Карта", "primary"),      ("👥 Отряды", "primary")],
        [("⚔️ В бой", "negative"),     ("🏪 Магазин", "positive")],
        [("🤝 Дипломатия", "secondary"),("📋 Квесты", "secondary")],
        [("🎒 Артефакты", "secondary"), ("📊 Статус", "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def screen_map(vk, p):
    text = "🗺 КАРТА ЗОНЫ\n────────────────\n"
    for sid, s in SECTORS.items():
        owner = "🟢" if sid in p["controlled_sectors"] else "⬜"
        lock = ""
        needed_warmth = sector_min_warmth(sid)
        if needed_warmth > p["warmth"]:
            lock = f" 🥶{needed_warmth}"
        if p["level"] < s["danger"]:
            lock = f" 🔒{s['danger']}ур"
        text += f"{owner} {sid}. {s['name']} | {s['temp']}°C | Опасность: {'☠'*s['danger']}{lock}\n"
    btns = []
    row = []
    for sid in SECTORS:
        label = f"{'✅' if sid in p['controlled_sectors'] else '📍'} {SECTORS[sid]['name']}"
        row.append((label[:40], "positive" if sid in p["controlled_sectors"] else "secondary"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_squads(vk, p):
    squads = [s for s in p["squads"] if s["alive"]]
    text = f"👥 ОТРЯДЫ ({len(squads)})\n────────────────\n"
    if not squads:
        text += "Нет живых отрядов. Наймите новых в магазине.\n"
    for i, s in enumerate(squads):
        power = squad_power(s, p["faction"])
        loc = SECTORS[s["sector"]]["name"] if s["sector"] else "База"
        text += (f"{i+1}. {s['unit_type']} x{s['count']} | 📍{loc}\n"
                 f"   ⚔️{power['attack']} 🛡{power['defense']} ❤️{power['hp']} 🌡{power['warmth']}\n"
                 f"   🔫{s.get('weapon','Кулаки')} | 🥼{s.get('armor','Нет')}\n")
    btns = []
    for i, s in enumerate(squads):
        btns.append([(f"Управление отрядом {i+1}", "primary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_squad_manage(vk, p, squad_idx):
    squads = [s for s in p["squads"] if s["alive"]]
    if squad_idx >= len(squads):
        screen_squads(vk, p)
        return
    s = squads[squad_idx]
    power = squad_power(s, p["faction"])
    loc = SECTORS[s["sector"]]["name"] if s["sector"] else "База"
    text = (
        f"👥 ОТРЯД {squad_idx+1}: {s['unit_type']} x{s['count']}\n"
        f"────────────────\n"
        f"📍 Позиция: {loc}\n"
        f"⚔️ Атака: {power['attack']} | 🛡 Защита: {power['defense']}\n"
        f"❤️ HP: {power['hp']} | 🌡 Тепло: {power['warmth']}\n"
        f"🔫 Оружие: {s.get('weapon','Кулаки')}\n"
        f"🥼 Броня: {s.get('armor','Нет')}\n"
        f"💎 Артефакты: {', '.join(s.get('artifacts',[])) or 'нет'}"
    )
    p["temp_selection"] = json.dumps({"squad_idx": squad_idx})
    save_player(p)
    btns = [
        [("🗺 Отправить в сектор", "primary")],
        [("🔫 Сменить оружие", "secondary"), ("🥼 Сменить броню", "secondary")],
        [("💎 Надеть артефакт", "secondary")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_shop(vk, p):
    text = f"🏪 МАГАЗИН\nЖетоны: {p['tokens']}\n────────────────\n"
    text += "ЮНИТЫ:\n"
    for name, u in UNIT_TYPES.items():
        lock = f" 🔒ур.{u['level_req']}" if p["level"] < u["level_req"] else ""
        text += f"• {name}: {u['cost']}жт | HP:{u['hp']} ⚔️{u['attack']}{lock}\n"
    text += "\nОРУЖИЕ:\n"
    for name, w in WEAPONS.items():
        if w["cost"] > 0:
            text += f"• {name}: {w['cost']}жт | +{w['attack']} атаки\n"
    text += "\nБРОНЯ:\n"
    for name, a in ARMORS.items():
        if a["cost"] > 0:
            text += f"• {name}: {a['cost']}жт | +{a['defense']} защ, +{a['warmth']} тепло\n"
    btns = [
        [("Нанять отряд", "positive")],
        [("Купить оружие", "primary"), ("Купить броню", "primary")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_hire(vk, p):
    text = f"👥 НАЙМ ОТРЯДА\nЖетоны: {p['tokens']}\n────────────────\n"
    btns = []
    for name, u in UNIT_TYPES.items():
        if p["level"] < u["level_req"]:
            continue
        if p["tokens"] < u["cost"]:
            btns.append([(f"❌ {name} ({u['cost']}жт)", "secondary")])
        else:
            btns.append([(f"Нанять: {name} ({u['cost']}жт)", "positive")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_buy_weapon(vk, p, squad_idx):
    squads = [s for s in p["squads"] if s["alive"]]
    text = f"🔫 ОРУЖИЕ\nЖетоны: {p['tokens']}\n────────────────\n"
    btns = []
    for name, w in WEAPONS.items():
        if w["cost"] == 0:
            continue
        label = f"{'❌ ' if p['tokens'] < w['cost'] else ''}{name} ({w['cost']}жт, +{w['attack']}⚔️)"
        color = "positive" if p["tokens"] >= w["cost"] else "secondary"
        btns.append([(label[:40], color)])
    btns.append([("◀️ Назад", "secondary")])
    p["temp_selection"] = json.dumps({"squad_idx": squad_idx, "buying": "weapon"})
    save_player(p)
    send(vk, p["vk_id"], text, kb(btns))

def screen_buy_armor(vk, p, squad_idx):
    text = f"🥼 БРОНЯ\nЖетоны: {p['tokens']}\n────────────────\n"
    btns = []
    for name, a in ARMORS.items():
        if a["cost"] == 0:
            continue
        label = f"{'❌ ' if p['tokens'] < a['cost'] else ''}{name} ({a['cost']}жт, +{a['warmth']}🌡)"
        color = "positive" if p["tokens"] >= a["cost"] else "secondary"
        btns.append([(label[:40], color)])
    btns.append([("◀️ Назад", "secondary")])
    p["temp_selection"] = json.dumps({"squad_idx": squad_idx, "buying": "armor"})
    save_player(p)
    send(vk, p["vk_id"], text, kb(btns))

def screen_artifacts(vk, p):
    text = f"💎 АРТЕФАКТЫ\nЖетоны: {p['tokens']}\n────────────────\n"
    if p["artifacts"]:
        text += "В хранилище:\n"
        counts = {}
        for a in p["artifacts"]:
            counts[a] = counts.get(a, 0) + 1
        for name, cnt in counts.items():
            art = ARTIFACTS[name]
            text += f"• {name} x{cnt} | ❤️+{art['hp_bonus']} ⚔️+{art['attack_bonus']} 🛡+{art['defense_bonus']} 🌡+{art['warmth_bonus']}\n"
    else:
        text += "Хранилище пусто.\n"
    text += "\nМОЖНО КУПИТЬ:\n"
    for name, art in ARTIFACTS.items():
        text += f"• {name}: {art['cost']}жт\n"
    btns = [
        [("Купить артефакт", "positive")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_diplomacy(vk, p):
    text = f"🤝 ДИПЛОМАТИЯ — {p['faction']}\n────────────────\n"
    base_relations = FACTIONS[p["faction"]]["relations"]
    for fname, base_rel in base_relations.items():
        current = p["diplomacy"].get(fname, base_rel)
        if current >= 50:
            status = "🟢 Союзник"
        elif current >= 10:
            status = "🔵 Нейтрал"
        elif current >= -20:
            status = "🟡 Напряжённо"
        else:
            status = "🔴 Война"
        text += f"{fname}: {status} ({current})\n"
    btns = [
        [("Объявить союз", "positive"), ("Объявить войну", "negative")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_status(vk, p):
    squads = [s for s in p["squads"] if s["alive"]]
    f = FACTIONS[p["faction"]]
    text = (
        f"📊 ДОСЬЕ: {p['name']}\n"
        f"────────────────\n"
        f"Фракция: {p['faction']}\n"
        f"Уровень: {p['level']} (опыт: {p['exp']}/{exp_for_next(p['level'])})\n"
        f"Жетоны: {p['tokens']}\n"
        f"Тепло: {p['warmth']}\n"
        f"Секторов: {len(p['controlled_sectors'])}/15\n"
        f"Отрядов: {len(squads)}\n"
        f"Артефактов: {len(p['artifacts'])}\n"
        f"Бонус фракции: {f['bonus']}"
    )
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def screen_quests(vk, p):
    text = "📋 КВЕСТЫ\n────────────────\n"
    if p["active_quest"]:
        text += f"▶️ Активный: {p['active_quest']}\nПрогресс: {p['quest_progress']}\n────────────────\n"
    done = p["completed_quests"]
    text += f"✅ Выполнено: {len(done)}\n\nДоступные квесты появляются при захвате секторов."
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

# ─── БОЙ ──────────────────────────────────────────────────────────────────────

def do_battle(vk, p, sector_id):
    s = SECTORS[sector_id]
    danger = s["danger"]
    squads = [sq for sq in p["squads"] if sq["alive"]]

    if not squads:
        send(vk, p["vk_id"], "Нет живых отрядов для атаки.", None)
        screen_main(vk, p)
        return

    squad = squads[0]
    power = squad_power(squad, p["faction"])

    # Температурный штраф
    temp_penalty = max(0, sector_min_warmth(sector_id) - power["warmth"])
    effective_defense = max(0, power["defense"] - temp_penalty)
    effective_attack = max(0, power["attack"] - temp_penalty // 2)

    # Враг
    enemy_pool = ENEMIES.get(min(danger, 6), ENEMIES[1])
    enemy_name, enemy_hp, enemy_dmg_range, enemy_exp, enemy_tokens_range = random.choice(enemy_pool)

    # Бой (авто, 5 раундов)
    player_hp = power["hp"]
    rounds = []
    for _ in range(5):
        if player_hp <= 0 or enemy_hp <= 0:
            break
        p_dmg = max(1, effective_attack + random.randint(-3, 5))
        e_dmg = max(0, random.randint(*enemy_dmg_range) - effective_defense)
        enemy_hp -= p_dmg
        player_hp -= e_dmg
        rounds.append(f"⚔️ {p_dmg} → 🐺 {e_dmg}")

    result_text = f"⚔️ БОЙ: {SECTORS[sector_id]['name']}\n{s['temp']}°C\n────────────────\n"
    result_text += f"Противник: {enemy_name}\n"
    result_text += "\n".join(rounds[:3]) + "\n────────────────\n"

    if enemy_hp <= 0:
        # Победа
        tokens_gain = random.randint(*enemy_tokens_range)
        # Бандиты получают +30%
        if p["faction"] == "Бандиты":
            tokens_gain = int(tokens_gain * 1.3)
        exp_gain = enemy_exp
        arts_found = []
        for _ in range(s["artifacts"]):
            if random.random() < 0.3:
                arts_found.append(random.choice(list(ARTIFACTS.keys())))

        p["tokens"] += tokens_gain
        p["exp"] += exp_gain
        if arts_found:
            p["artifacts"].extend(arts_found)
        if sector_id not in p["controlled_sectors"]:
            p["controlled_sectors"].append(sector_id)
        squad["sector"] = sector_id

        levelup_msgs = try_levelup(p)

        result_text += f"✅ ПОБЕДА!\n+{tokens_gain} жетонов | +{exp_gain} опыта\n"
        if arts_found:
            result_text += f"💎 Найдены артефакты: {', '.join(arts_found)}\n"
        for lm in levelup_msgs:
            result_text += f"\n{lm}"

        # Проверка победы в игре
        if len(p["controlled_sectors"]) >= 15:
            result_text += "\n\n🏆 ТЫ ЗАХВАТИЛ ВСЮ ЗОНУ! Победа!"
    else:
        # Поражение
        penalty = int(p["tokens"] * 0.1)
        p["tokens"] = max(0, p["tokens"] - penalty)
        if player_hp <= 0 and len(squads) == 1:
            squad["alive"] = False
            result_text += f"💀 ОТРЯД УНИЧТОЖЕН (permadeath)\n"
        result_text += f"💔 ПОРАЖЕНИЕ. -{penalty} жетонов.\n"

    # Выброс: урон если активен
    if blowout_active(p):
        blowout_dmg = danger * 10
        p["tokens"] = max(0, p["tokens"] - blowout_dmg)
        result_text += f"\n⚡️ Выброс нанёс {blowout_dmg} урона по жетонам!"

    save_player(p)
    send(vk, p["vk_id"], result_text, kb([
        [("⚔️ Ещё раз", "negative"), ("◀️ В лагерь", "secondary")]
    ]))

# ─── ВЫБОР ФРАКЦИИ ────────────────────────────────────────────────────────────

def screen_choose_faction(vk, p):
    text = "☢️ ВЫБОР ФРАКЦИИ\n────────────────\nВыбери свою группировку:"
    btns = []
    row = []
    for name in FACTIONS:
        row.append((name, "primary"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    send(vk, p["vk_id"], text, kb(btns))

def screen_faction_info(vk, p, faction_name):
    f = FACTIONS[faction_name]
    text = (
        f"☢️ {faction_name}\n"
        f"────────────────\n"
        f"{f['desc']}\n\n"
        f"Бонус: {f['bonus']}\n"
        f"Стартовые жетоны: {f['start_tokens']}\n"
        f"Тепло: +{f['start_warmth']}\n"
        f"Атака: {'+' if f['attack_bonus'] >= 0 else ''}{f['attack_bonus']}\n"
        f"Защита: {'+' if f['defense_bonus'] >= 0 else ''}{f['defense_bonus']}"
    )
    p["temp_selection"] = json.dumps({"pending_faction": faction_name})
    save_player(p)
    send(vk, p["vk_id"], text, kb([
        [(f"✅ Выбрать {faction_name}", "positive")],
        [("◀️ Другая фракция", "secondary")],
    ]))

# ─── ОБРАБОТЧИК СООБЩЕНИЙ ─────────────────────────────────────────────────────

def handle_message(vk, vk_id, text):
    text = text.strip()
    p = get_player(vk_id)

    if not p:
        create_player(vk_id)
        p = get_player(vk_id)
        send(vk, vk_id,
             "❄️ ЗОНА. ЯДЕРНАЯ ЗИМА.\n────────────────\n"
             "Температура в эпицентре достигает -200°C.\n"
             "Выживают только сильнейшие фракции.\n\n"
             "Как тебя зовут, сталкер?",
             kb([[("Начать", "positive")]]))
        return

    state = p["state"]

    # ── Ввод имени ──
    if state == "start":
        if text == "Начать":
            send(vk, vk_id, "Введи своё имя:", None)
            return
        if text.startswith(tuple("📊🗺👥⚔️🏪🤝📋🎒◀️")):
            send(vk, vk_id, "Сначала введи имя.", None)
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
        sel = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
        if text.startswith("✅ Выбрать "):
            fname = text[10:]
            if fname in FACTIONS:
                f = FACTIONS[fname]
                p["faction"] = fname
                p["tokens"] = f["start_tokens"]
                p["warmth"] = f["start_warmth"]
                p["controlled_sectors"] = [1]
                p["squads"] = [new_squad("Новобранец"), new_squad("Новобранец")]
                p["diplomacy"] = dict(f["relations"])
                p["state"] = "main"
                p["blowout_next"] = int(time.time()) + 900
                save_player(p)
                send(vk, vk_id,
                     f"✅ Фракция выбрана: {fname}\n"
                     f"База: Кордон (-5°C)\n"
                     f"Отряды: 2 x Новобранец\n"
                     f"Жетоны: {f['start_tokens']}\n\n"
                     f"Захвати все 15 секторов. Удачи.", None)
                screen_main(vk, p)
                return
        if text == "◀️ Другая фракция":
            screen_choose_faction(vk, p)
            return
        screen_choose_faction(vk, p)
        return

    # ── Главное меню ──
    if text in ("◀️ Назад", "◀️ В лагерь", "В лагерь"):
        screen_main(vk, p)
        return

    if text == "🗺 Карта":
        screen_map(vk, p)
        return

    if text == "👥 Отряды":
        screen_squads(vk, p)
        return

    if text == "📊 Статус":
        screen_status(vk, p)
        return

    if text == "🏪 Магазин":
        screen_shop(vk, p)
        return

    if text == "🤝 Дипломатия":
        screen_diplomacy(vk, p)
        return

    if text == "📋 Квесты":
        screen_quests(vk, p)
        return

    if text == "🎒 Артефакты":
        screen_artifacts(vk, p)
        return

    # ── Магазин ──
    if text == "Нанять отряд":
        screen_hire(vk, p)
        return

    if text.startswith("Нанять: "):
        unit_name = text[8:].split(" (")[0]
        unit = UNIT_TYPES.get(unit_name)
        if not unit:
            screen_hire(vk, p)
            return
        if p["tokens"] < unit["cost"]:
            send(vk, vk_id, f"Не хватает жетонов. Нужно {unit['cost']}.", None)
            screen_hire(vk, p)
            return
        if p["level"] < unit["level_req"]:
            send(vk, vk_id, f"Нужен {unit['level_req']} уровень.", None)
            screen_hire(vk, p)
            return
        p["tokens"] -= unit["cost"]
        p["squads"].append(new_squad(unit_name))
        save_player(p)
        send(vk, vk_id, f"✅ Нанят отряд: {unit_name}.", None)
        screen_main(vk, p)
        return

    if text == "Купить оружие":
        sel = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
        screen_buy_weapon(vk, p, sel.get("squad_idx", 0))
        return

    if text == "Купить броню":
        sel = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
        screen_buy_armor(vk, p, sel.get("squad_idx", 0))
        return

    # Покупка оружия/брони для отряда
    sel = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
    if text.startswith("Нанять:") is False:
        # Проверяем покупку оружия
        for wname, w in WEAPONS.items():
            if wname in text and w["cost"] > 0:
                buying = sel.get("buying")
                squad_idx = sel.get("squad_idx", 0)
                squads = [s for s in p["squads"] if s["alive"]]
                if buying == "weapon" and squad_idx < len(squads):
                    if p["tokens"] < w["cost"]:
                        send(vk, vk_id, f"Не хватает жетонов.", None)
                        screen_buy_weapon(vk, p, squad_idx)
                        return
                    p["tokens"] -= w["cost"]
                    squads[squad_idx]["weapon"] = wname
                    save_player(p)
                    send(vk, vk_id, f"✅ {squads[squad_idx]['unit_type']} вооружён: {wname}.", None)
                    screen_squad_manage(vk, p, squad_idx)
                    return

        # Проверяем покупку брони
        for aname, a in ARMORS.items():
            if aname in text and a["cost"] > 0:
                buying = sel.get("buying")
                squad_idx = sel.get("squad_idx", 0)
                squads = [s for s in p["squads"] if s["alive"]]
                if buying == "armor" and squad_idx < len(squads):
                    if p["tokens"] < a["cost"]:
                        send(vk, vk_id, f"Не хватает жетонов.", None)
                        screen_buy_armor(vk, p, squad_idx)
                        return
                    p["tokens"] -= a["cost"]
                    squads[squad_idx]["armor"] = aname
                    p["warmth"] = max(p["warmth"], a["warmth"])
                    save_player(p)
                    send(vk, vk_id, f"✅ Броня надета: {aname}. Тепло: {p['warmth']}.", None)
                    screen_squad_manage(vk, p, squad_idx)
                    return

    # ── Управление отрядами ──
    if text.startswith("Управление отрядом "):
        try:
            idx = int(text.split()[-1]) - 1
            screen_squad_manage(vk, p, idx)
        except Exception:
            screen_squads(vk, p)
        return

    if text == "🗺 Отправить в сектор":
        text2 = "📍 ВЫБЕРИ СЕКТОР ДЛЯ АТАКИ\n────────────────\n"
        btns = []
        row = []
        for sid, s in SECTORS.items():
            needed = sector_min_warmth(sid)
            lock = f" 🥶{needed}" if needed > p["warmth"] else ""
            lock = lock or (f" 🔒{s['danger']}ур" if p["level"] < s["danger"] else "")
            label = f"{'✅' if sid in p['controlled_sectors'] else '⚔️'} {s['name']}{lock}"
            row.append((label[:40], "positive" if sid in p["controlled_sectors"] else "negative"))
            if len(row) == 2:
                btns.append(row)
                row = []
        if row:
            btns.append(row)
        btns.append([("◀️ Назад", "secondary")])
        send(vk, p["vk_id"], text2, kb(btns))
        return

    if text == "🔫 Сменить оружие":
        sel2 = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
        screen_buy_weapon(vk, p, sel2.get("squad_idx", 0))
        return

    if text == "🥼 Сменить броню":
        sel2 = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
        screen_buy_armor(vk, p, sel2.get("squad_idx", 0))
        return

    # ── Атака сектора ──
    if text == "⚔️ В бой" or text == "⚔️ Ещё раз":
        # Идём в ближайший незахваченный сектор
        uncaptured = [sid for sid in SECTORS if sid not in p["controlled_sectors"]]
        if not uncaptured:
            send(vk, vk_id, "Все сектора захвачены! Ты победил!", None)
            return
        # Выбираем ближайший к базе
        target = min(uncaptured, key=lambda x: abs(x - p["home_sector"]))
        do_battle(vk, p, target)
        return

    # Атака конкретного сектора с карты
    for sid, s in SECTORS.items():
        if f"⚔️ {s['name']}" in text or f"✅ {s['name']}" in text:
            if p["level"] < s["danger"]:
                send(vk, vk_id, f"🔒 Нужен {s['danger']} уровень.", None)
                screen_map(vk, p)
                return
            needed = sector_min_warmth(sid)
            if needed > p["warmth"]:
                send(vk, vk_id, f"🥶 Нужно тепло {needed}. Купи броню.", None)
                screen_map(vk, p)
                return
            do_battle(vk, p, sid)
            return

    # ── Дипломатия ──
    if text == "Объявить союз":
        text3 = "🤝 С кем заключить союз?\n"
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_selection"] = json.dumps({"diplo": "ally"})
        save_player(p)
        send(vk, p["vk_id"], text3, kb(btns))
        return

    if text == "Объявить войну":
        text4 = "⚔️ На кого объявить войну?\n"
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_selection"] = json.dumps({"diplo": "war"})
        save_player(p)
        send(vk, p["vk_id"], text4, kb(btns))
        return

    # Применение дипломатии
    diplo_sel = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
    if diplo_sel.get("diplo") and text in FACTIONS:
        action = diplo_sel["diplo"]
        if action == "ally":
            p["diplomacy"][text] = min(100, p["diplomacy"].get(text, 0) + 40)
            save_player(p)
            send(vk, vk_id, f"🤝 Союз с {text} заключён. Отношения: {p['diplomacy'][text]}.", None)
        elif action == "war":
            p["diplomacy"][text] = max(-100, p["diplomacy"].get(text, 0) - 60)
            save_player(p)
            send(vk, vk_id, f"⚔️ Война с {text} объявлена. Отношения: {p['diplomacy'][text]}.", None)
        screen_main(vk, p)
        return

    # ── Артефакты: покупка ──
    if text == "Купить артефакт":
        text5 = f"💎 КУПИТЬ АРТЕФАКТ\nЖетоны: {p['tokens']}\n────────────────\n"
        btns = []
        for name, art in ARTIFACTS.items():
            label = f"{'❌ ' if p['tokens'] < art['cost'] else ''}{name} ({art['cost']}жт)"
            color = "positive" if p["tokens"] >= art["cost"] else "secondary"
            btns.append([(label[:40], color)])
        btns.append([("◀️ Назад", "secondary")])
        send(vk, p["vk_id"], text5, kb(btns))
        return

    for aname, art in ARTIFACTS.items():
        if aname in text and art["cost"] > 0:
            if p["tokens"] < art["cost"]:
                send(vk, vk_id, f"Не хватает жетонов.", None)
                return
            p["tokens"] -= art["cost"]
            p["artifacts"].append(aname)
            save_player(p)
            send(vk, vk_id, f"✅ Артефакт куплен: {aname}.", None)
            screen_main(vk, p)
            return

    # ── Артефакт на отряд ──
    if text == "💎 Надеть артефакт":
        if not p["artifacts"]:
            send(vk, vk_id, "Нет артефактов в хранилище.", None)
            return
        sel3 = json.loads(p["temp_selection"]) if p["temp_selection"] else {}
        squad_idx = sel3.get("squad_idx", 0)
        squads = [s for s in p["squads"] if s["alive"]]
        if squad_idx < len(squads):
            art_name = p["artifacts"].pop(0)
            squads[squad_idx].setdefault("artifacts", []).append(art_name)
            save_player(p)
            send(vk, vk_id, f"✅ {art_name} надет на отряд.", None)
            screen_squad_manage(vk, p, squad_idx)
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
