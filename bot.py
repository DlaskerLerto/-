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
DB_PATH = "game4.db"

# ═══════════════════════════════════════════════════════════════
# ИГРОВЫЕ ДАННЫЕ
# ═══════════════════════════════════════════════════════════════

FACTIONS = {
    "Сталкеры": {
        "desc": "Вольные бродяги. Живут по законам Зоны, никому не подчиняются.",
        "bonus": "+5 защиты. Разведка соседних секторов.",
        "start_tokens": 150, "start_warmth": 10,
        "attack_bonus": 0, "defense_bonus": 5,
        "ranks": ["Новичок", "Сталкер", "Опытный", "Мастер", "Легенда Зоны"],
    },
    "Долг": {
        "desc": "Военизированная группировка. Дисциплина и огонь.",
        "bonus": "+10 защиты, +5 атаки.",
        "start_tokens": 120, "start_warmth": 15,
        "attack_bonus": 5, "defense_bonus": 10,
        "ranks": ["Рядовой", "Ефрейтор", "Сержант", "Лейтенант", "Полковник"],
    },
    "Свобода": {
        "desc": "Анархисты. Быстрые и непредсказуемые.",
        "bonus": "+10 атаки. Захват секторов на 20% быстрее.",
        "start_tokens": 130, "start_warmth": 5,
        "attack_bonus": 10, "defense_bonus": 0,
        "ranks": ["Фраер", "Боец", "Старший боец", "Командир", "Барон Зоны"],
    },
    "Бандиты": {
        "desc": "Мародёры и головорезы. Богатеют за счёт слабых.",
        "bonus": "+30% жетонов с боёв. +15 атаки.",
        "start_tokens": 200, "start_warmth": 0,
        "attack_bonus": 15, "defense_bonus": -5,
        "ranks": ["Шестёрка", "Быдло", "Бандит", "Авторитет", "Пахан"],
    },
    "Военные": {
        "desc": "Армейские части. Тяжёлое снаряжение, железная дисциплина.",
        "bonus": "+15 защиты, +10 атаки.",
        "start_tokens": 100, "start_warmth": 20,
        "attack_bonus": 10, "defense_bonus": 15,
        "ranks": ["Рядовой", "Капрал", "Старшина", "Капитан", "Генерал"],
    },
    "Монолит": {
        "desc": "Фанатики. Служат Монолиту. Не боятся ни холода, ни смерти.",
        "bonus": "Иммунитет к выбросам. +20 атаки, +10 защиты.",
        "start_tokens": 80, "start_warmth": 30,
        "attack_bonus": 20, "defense_bonus": 10,
        "ranks": ["Послушник", "Адепт", "Воин Монолита", "Страж", "Голос Монолита"],
    },
    "Наёмники": {
        "desc": "Профессионалы. Работают на того, кто платит.",
        "bonus": "+250 стартовых жетонов. +10 атаки, +5 защиты.",
        "start_tokens": 250, "start_warmth": 10,
        "attack_bonus": 10, "defense_bonus": 5,
        "ranks": ["Контрактник", "Оперативник", "Специалист", "Эксперт", "Призрак"],
    },
    "Экологи": {
        "desc": "Учёные института. Слабы в бою, но лучшие знатоки артефактов.",
        "bonus": "x2 эффект артефактов.",
        "start_tokens": 120, "start_warmth": 15,
        "attack_bonus": -5, "defense_bonus": 5,
        "ranks": ["Лаборант", "Исследователь", "Старший учёный", "Профессор", "Академик"],
    },
    "Ренегаты": {
        "desc": "Дезертиры всех сторон. Знают тактику каждой группировки.",
        "bonus": "15% шанс диверсии (враг теряет ход). +15 атаки.",
        "start_tokens": 140, "start_warmth": 5,
        "attack_bonus": 15, "defense_bonus": -10,
        "ranks": ["Перебежчик", "Отступник", "Ренегат", "Командир ренегатов", "Тень Зоны"],
    },
    "Чистое Небо": {
        "desc": "Борцы с аномалиями. Мечтают очистить Зону.",
        "bonus": "-50% урона от радиации. +5 атаки, +10 защиты.",
        "start_tokens": 130, "start_warmth": 20,
        "attack_bonus": 5, "defense_bonus": 10,
        "ranks": ["Кандидат", "Боец", "Ветеран", "Командир", "Основатель"],
    },
}

BASE_RELATIONS = {
    "Сталкеры":    {"Долг": 20,  "Свобода": 40,  "Бандиты": -30, "Военные": -10, "Монолит": -50, "Наёмники": 0,   "Экологи": 30,  "Ренегаты": -40, "Чистое Небо": 20},
    "Долг":        {"Сталкеры": 20, "Свобода": -40, "Бандиты": -50, "Военные": 30, "Монолит": -60, "Наёмники": -10, "Экологи": 10,  "Ренегаты": -50, "Чистое Небо": 30},
    "Свобода":     {"Сталкеры": 40, "Долг": -40,  "Бандиты": -20, "Военные": -30, "Монолит": -50, "Наёмники": 10,  "Экологи": 20,  "Ренегаты": -20, "Чистое Небо": 10},
    "Бандиты":     {"Сталкеры": -30,"Долг": -50,  "Свобода": -20, "Военные": -40, "Монолит": -30, "Наёмники": 20,  "Экологи": -20, "Ренегаты": 30,  "Чистое Небо": -30},
    "Военные":     {"Сталкеры": -10,"Долг": 30,   "Свобода": -30, "Бандиты": -40, "Монолит": -60, "Наёмники": -20, "Экологи": 20,  "Ренегаты": -50, "Чистое Небо": 20},
    "Монолит":     {"Сталкеры": -50,"Долг": -60,  "Свобода": -50, "Бандиты": -30, "Военные": -60, "Наёмники": -40, "Экологи": -30, "Ренегаты": -20, "Чистое Небо": -50},
    "Наёмники":    {"Сталкеры": 0,  "Долг": -10,  "Свобода": 10,  "Бандиты": 20,  "Военные": -20, "Монолит": -40,  "Экологи": 10,  "Ренегаты": 10,  "Чистое Небо": 0},
    "Экологи":     {"Сталкеры": 30, "Долг": 10,   "Свобода": 20,  "Бандиты": -20, "Военные": 20,  "Монолит": -30,  "Наёмники": 10, "Ренегаты": -30, "Чистое Небо": 30},
    "Ренегаты":    {"Сталкеры": -40,"Долг": -50,  "Свобода": -20, "Бандиты": 30,  "Военные": -50, "Монолит": -20,  "Наёмники": 10, "Экологи": -30,  "Чистое Небо": -20},
    "Чистое Небо": {"Сталкеры": 20, "Долг": 30,   "Свобода": 10,  "Бандиты": -30, "Военные": 20,  "Монолит": -50,  "Наёмники": 0,  "Экологи": 30,   "Ренегаты": -20},
}

# Локации → список секторов
LOCATIONS = {
    "Приграничье": {
        "desc": "Окраина Зоны. Тут ещё теплее. Новички, мелкие банды.",
        "sectors": [1, 2, 3],
        "temp_range": (-5, -15),
    },
    "Промзона": {
        "desc": "Заброшенные заводы и свалки. Здесь начинается настоящая Зона.",
        "sectors": [4, 5, 6, 7],
        "temp_range": (-18, -30),
    },
    "Глубокая Зона": {
        "desc": "Мёртвые города и аномальные поля. Без снаряжения — смерть.",
        "sectors": [8, 9, 10],
        "temp_range": (-45, -65),
    },
    "Тёмные территории": {
        "desc": "Постоянный туман. Аномалии повсюду. Видимость — ноль.",
        "sectors": [11, 12],
        "temp_range": (-75, -100),
    },
    "Эпицентр": {
        "desc": "Самое опасное место на Земле. Температура достигает -200°C.",
        "sectors": [13, 14, 15],
        "temp_range": (-120, -200),
    },
}

SECTORS = {
    1:  {"name": "Кордон",            "location": "Приграничье",    "temp": -5,   "danger": 1, "tokens": 30,  "artifacts": 1,  "has_trader": True},
    2:  {"name": "Свалка",            "location": "Приграничье",    "temp": -12,  "danger": 1, "tokens": 35,  "artifacts": 1,  "has_trader": True},
    3:  {"name": "База новичков",     "location": "Приграничье",    "temp": -8,   "danger": 1, "tokens": 20,  "artifacts": 0,  "has_trader": True},
    4:  {"name": "Агропром",          "location": "Промзона",       "temp": -18,  "danger": 2, "tokens": 50,  "artifacts": 2,  "has_trader": True},
    5:  {"name": "Тёмная долина",     "location": "Промзона",       "temp": -22,  "danger": 2, "tokens": 55,  "artifacts": 2,  "has_trader": True},
    6:  {"name": "Ржавые пустоши",    "location": "Промзона",       "temp": -28,  "danger": 2, "tokens": 60,  "artifacts": 2,  "has_trader": False},
    7:  {"name": "100 рентген",       "location": "Промзона",       "temp": -25,  "danger": 2, "tokens": 70,  "artifacts": 1,  "has_trader": True},
    8:  {"name": "Мёртвый город",     "location": "Глубокая Зона",  "temp": -45,  "danger": 3, "tokens": 90,  "artifacts": 3,  "has_trader": True},
    9:  {"name": "Радар",             "location": "Глубокая Зона",  "temp": -55,  "danger": 3, "tokens": 100, "artifacts": 3,  "has_trader": False},
    10: {"name": "Янтарь",            "location": "Глубокая Зона",  "temp": -60,  "danger": 3, "tokens": 110, "artifacts": 4,  "has_trader": True},
    11: {"name": "Туманный провал",   "location": "Тёмные территории","temp": -75,"danger": 4, "tokens": 140, "artifacts": 4,  "has_trader": False},
    12: {"name": "Саркофаг",          "location": "Тёмные территории","temp": -95,"danger": 4, "tokens": 160, "artifacts": 5,  "has_trader": True},
    13: {"name": "Припять",           "location": "Эпицентр",       "temp": -120, "danger": 5, "tokens": 200, "artifacts": 5,  "has_trader": False},
    14: {"name": "ЧАЭС",              "location": "Эпицентр",       "temp": -155, "danger": 5, "tokens": 250, "artifacts": 6,  "has_trader": False},
    15: {"name": "Ледяное сердце",    "location": "Эпицентр",       "temp": -200, "danger": 6, "tokens": 400, "artifacts": 8,  "has_trader": False},
}

def get_location_of_sector(sid):
    return SECTORS[sid]["location"]

# Торговцы — ассортимент по локации
TRADER_STOCK = {
    "Приграничье": {
        "weapons": ["Охотничий нож", "ПМ", "АКС-74У"],
        "armors":  ["Куртка новичка", "Телогрейка", "Зимний костюм"],
        "items":   ["Бинт", "Аптечка", "Хлеб", "Консервы"],
        "artifacts":["Медуза"],
    },
    "Промзона": {
        "weapons": ["ПМ", "АКС-74У", "АК-74", "Дробовик"],
        "armors":  ["Зимний костюм", "SEVA-костюм"],
        "items":   ["Аптечка", "Армейская аптечка", "Антирад", "Консервы"],
        "artifacts":["Медуза", "Огненный шар", "Кристалл"],
    },
    "Глубокая Зона": {
        "weapons": ["АК-74", "СВД", "РПГ-7"],
        "armors":  ["SEVA-костюм", "Экзоскелет-С"],
        "items":   ["Армейская аптечка", "Антирад", "Стимулятор"],
        "artifacts":["Огненный шар", "Кристалл", "Морской ёж", "Пружина"],
    },
    "Тёмные территории": {
        "weapons": ["СВД", "РПГ-7", "Гаусс-пушка"],
        "armors":  ["Экзоскелет-С", "Криокостюм Mk.I"],
        "items":   ["Армейская аптечка", "Стимулятор", "Антирад"],
        "artifacts":["Морской ёж", "Пружина", "Мамины бусы"],
    },
}

WEAPONS = {
    "Кулаки":          {"attack": 0,   "cost": 0,    "desc": "Голые руки. Лучше, чем ничего."},
    "Охотничий нож":   {"attack": 8,   "cost": 30,   "desc": "Надёжный нож. Тихий и смертоносный вблизи."},
    "ПМ":              {"attack": 15,  "cost": 80,   "desc": "Пистолет Макарова. Классика выживания."},
    "АКС-74У":         {"attack": 28,  "cost": 200,  "desc": "Укороченный автомат. Лёгкий и скорострельный."},
    "Дробовик":        {"attack": 35,  "cost": 280,  "desc": "Убийственен в упор. Против мутантов — идеал."},
    "АК-74":           {"attack": 40,  "cost": 350,  "desc": "Основной автомат Зоны. Надёжен в любых условиях."},
    "СВД":             {"attack": 60,  "cost": 600,  "desc": "Снайперская винтовка. Бьёт издалека."},
    "РПГ-7":           {"attack": 90,  "cost": 1100, "desc": "Гранатомёт. Для серьёзных противников."},
    "Гаусс-пушка":     {"attack": 140, "cost": 2500, "desc": "Экспериментальное оружие. Разрывает всё."},
}

ARMORS = {
    "Нет":              {"defense": 0,  "warmth": 0,   "cost": 0,    "desc": "Без защиты. Холод убьёт быстрее врага."},
    "Куртка новичка":   {"defense": 5,  "warmth": 10,  "cost": 50,   "desc": "Простая куртка. Хоть что-то."},
    "Телогрейка":       {"defense": 8,  "warmth": 20,  "cost": 80,   "desc": "Тёплая, но не защищает от пуль."},
    "Зимний костюм":    {"defense": 14, "warmth": 35,  "cost": 180,  "desc": "Специальный костюм для холодов Зоны."},
    "SEVA-костюм":      {"defense": 22, "warmth": 55,  "cost": 450,  "desc": "Научный костюм. Защищает от аномалий."},
    "Экзоскелет-С":     {"defense": 35, "warmth": 75,  "cost": 900,  "desc": "Силовой экзоскелет. Мощь и защита."},
    "Криокостюм Mk.I":  {"defense": 50, "warmth": 100, "cost": 1800, "desc": "Разработан для Эпицентра. Выдерживает -100°C."},
    "Криокостюм Mk.II": {"defense": 65, "warmth": 125, "cost": 3000, "desc": "Улучшенная версия. Выдерживает -150°C."},
    "Абсолют":          {"defense": 85, "warmth": 155, "cost": 6000, "desc": "Легендарная броня. Только для Ледяного сердца."},
}

CONSUMABLES = {
    "Бинт":            {"hp_restore": 25,  "cost": 15,  "desc": "Останавливает кровотечение. +25 HP."},
    "Хлеб":            {"hp_restore": 15,  "cost": 10,  "desc": "Чёрствый хлеб. Немного восстанавливает силы."},
    "Консервы":        {"hp_restore": 30,  "cost": 20,  "desc": "Тушёнка. Питательно и надолго."},
    "Аптечка":         {"hp_restore": 60,  "cost": 50,  "desc": "Медицинская аптечка. +60 HP."},
    "Армейская аптечка":{"hp_restore": 120, "cost": 120, "desc": "Армейский набор. +120 HP. Быстрое применение."},
    "Антирад":         {"hp_restore": 0,   "cost": 80,  "desc": "Нейтрализует радиацию. Без него в Эпицентре смерть."},
    "Стимулятор":      {"hp_restore": 0,   "cost": 100, "desc": "+20 атаки на следующий бой. Временный эффект."},
}

ARTIFACTS = {
    "Медуза":       {"hp_bonus": 30,  "attack_bonus": 0,  "defense_bonus": 0,  "warmth_bonus": 0,  "cost": 100, "desc": "Пульсирует. Восстанавливает HP. +30 макс.HP."},
    "Огненный шар": {"hp_bonus": 0,   "attack_bonus": 18, "defense_bonus": 0,  "warmth_bonus": 8,  "cost": 150, "desc": "Горячий. +18 атаки, +8 тепла."},
    "Кристалл":     {"hp_bonus": 0,   "attack_bonus": 0,  "defense_bonus": 12, "warmth_bonus": 12, "cost": 180, "desc": "Твёрдый как броня. +12 защиты, +12 тепла."},
    "Морской ёж":   {"hp_bonus": 60,  "attack_bonus": 12, "defense_bonus": 8,  "warmth_bonus": 0,  "cost": 250, "desc": "Универсальный артефакт. Всё понемногу."},
    "Пружина":      {"hp_bonus": 0,   "attack_bonus": 30, "defense_bonus": 0,  "warmth_bonus": 0,  "cost": 300, "desc": "Концентрирует силу удара. +30 атаки."},
    "Мамины бусы":  {"hp_bonus": 25,  "attack_bonus": 0,  "defense_bonus": 25, "warmth_bonus": 25, "cost": 500, "desc": "Загадочный артефакт. Даёт тепло и защиту."},
    "Душа":         {"hp_bonus": 120, "attack_bonus": 25, "defense_bonus": 25, "warmth_bonus": 35, "cost": 1000,"desc": "Редчайший артефакт. Меняет носителя навсегда."},
}

ENEMIES = {
    1: [("🐕 Одичавшая собака", 30,  (4, 10),  10,  (5, 15),   "Больно кусает. Быстрая."),
        ("🔪 Мародёр",          40,  (6, 14),  15,  (10, 25),  "Вооружён ножом. Трусливый.")],
    2: [("🧟 Зомби-солдат",     70,  (10, 18), 25,  (20, 45),  "Медленный, но живучий."),
        ("🩸 Кровосос",         90,  (14, 24), 35,  (35, 60),  "Пьёт кровь. Невидим в тумане.")],
    3: [("🦍 Псевдогигант",     160, (22, 38), 55,  (65, 110), "Огромный мутант. Крушит всё."),
        ("🧠 Контролёр",        110, (18, 32), 45,  (55, 95),  "Подчиняет разум. Смотри в глаза.")],
    4: [("🐆 Химера",           200, (30, 50), 80,  (95, 160), "Два сросшихся мутанта. Быстрая."),
        ("👻 Полтергейст",       130, (25, 45), 60,  (75, 130), "Кидает предметы. Невидим.")],
    5: [("⚔️ Страж Зоны",       300, (45, 70), 100, (160, 260),"Элитный солдат Монолита."),
        ("💀 Излом",            240, (38, 62), 90,  (130, 210),"Высший мутант. Не знает боли.")],
    6: [("☠️ Вечный страж",     420, (65, 100),130, (260, 420),"Легендарный монстр Эпицентра."),
        ("🔮 Монолитовец",       320, (55, 85), 110, (210, 360),"Фанатик с тяжёлым вооружением.")],
}

# ═══════════════════════════════════════════════════════════════
# БАЗА ДАННЫХ
# ═══════════════════════════════════════════════════════════════

def init_db():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        vk_id              INTEGER PRIMARY KEY,
        name               TEXT DEFAULT '__new__',
        state              TEXT DEFAULT 'tutorial_0',
        faction            TEXT DEFAULT '',
        faction_rank       INTEGER DEFAULT 0,
        faction_rep        INTEGER DEFAULT 0,
        level              INTEGER DEFAULT 1,
        exp                INTEGER DEFAULT 0,
        tokens             INTEGER DEFAULT 0,
        hp                 INTEGER DEFAULT 100,
        max_hp             INTEGER DEFAULT 100,
        attack             INTEGER DEFAULT 10,
        defense            INTEGER DEFAULT 0,
        warmth             INTEGER DEFAULT 0,
        weapon             TEXT DEFAULT 'Охотничий нож',
        armor              TEXT DEFAULT 'Нет',
        equipped_artifacts TEXT DEFAULT '[]',
        stored_artifacts   TEXT DEFAULT '[]',
        inventory          TEXT DEFAULT '[]',
        current_sector     INTEGER DEFAULT 1,
        controlled_sectors TEXT DEFAULT '[]',
        diplomacy          TEXT DEFAULT '{}',
        battle_state       TEXT DEFAULT '{}',
        active_quest       TEXT DEFAULT '',
        quest_progress     INTEGER DEFAULT 0,
        completed_quests   TEXT DEFAULT '[]',
        stim_active        INTEGER DEFAULT 0,
        capture_sector     INTEGER DEFAULT 0,
        capture_end        INTEGER DEFAULT 0,
        temp_state         TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS global_blowout (
        id       INTEGER PRIMARY KEY DEFAULT 1,
        next_ts  INTEGER DEFAULT 0,
        active   INTEGER DEFAULT 0,
        end_ts   INTEGER DEFAULT 0
    )""")
    c.execute("INSERT OR IGNORE INTO global_blowout (id, next_ts) VALUES (1, ?)",
              (int(time.time()) + 900,))
    con.commit()
    con.close()

def get_blowout():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = con.cursor()
    c.execute("SELECT * FROM global_blowout WHERE id=1")
    row = dict(c.fetchone())
    con.close()
    return row

def set_blowout(next_ts, active, end_ts):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("UPDATE global_blowout SET next_ts=?, active=?, end_ts=? WHERE id=1",
              (next_ts, active, end_ts))
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
    for f in ("equipped_artifacts", "stored_artifacts", "inventory",
              "controlled_sectors", "diplomacy", "completed_quests", "battle_state"):
        p[f] = json.loads(p[f])
    return p

def save_player(p):
    data = dict(p)
    for f in ("equipped_artifacts", "stored_artifacts", "inventory",
              "controlled_sectors", "diplomacy", "completed_quests", "battle_state"):
        data[f] = json.dumps(p[f])
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

def get_all_players():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = con.cursor()
    c.execute("SELECT vk_id, faction, current_sector, controlled_sectors FROM players WHERE state='main'")
    rows = [dict(r) for r in c.fetchall()]
    con.close()
    return rows

# ═══════════════════════════════════════════════════════════════
# VK ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════════

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

def notify_players(vk, vk_ids, text):
    for vid in vk_ids:
        try:
            send(vk, vid, text)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
# ИГРОВЫЕ ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════════

def calc_stats(p):
    f = FACTIONS.get(p["faction"], {})
    w = WEAPONS.get(p["weapon"], WEAPONS["Охотничий нож"])
    a = ARMORS.get(p["armor"], ARMORS["Нет"])
    attack = 10 + w["attack"] + f.get("attack_bonus", 0)
    defense = a["defense"] + f.get("defense_bonus", 0)
    warmth = a["warmth"] + f.get("start_warmth", 0)
    max_hp = 100
    multiplier = 2 if p["faction"] == "Экологи" else 1
    for art_name in p["equipped_artifacts"]:
        art = ARTIFACTS.get(art_name, {})
        attack += art.get("attack_bonus", 0) * multiplier
        defense += art.get("defense_bonus", 0) * multiplier
        warmth += art.get("warmth_bonus", 0) * multiplier
        max_hp += art.get("hp_bonus", 0) * multiplier
    if p.get("stim_active"):
        attack += 20
    return {"attack": attack, "defense": defense, "warmth": warmth, "max_hp": max_hp}

def sector_min_warmth(sid):
    return max(0, -SECTORS[sid]["temp"] // 3)

def exp_for_next(level):
    return level * 150

def rep_for_rank(rank):
    return rank * 200

def try_levelup(p):
    msgs = []
    while p["exp"] >= exp_for_next(p["level"]):
        p["exp"] -= exp_for_next(p["level"])
        p["level"] += 1
        p["max_hp"] += 20
        p["hp"] = min(p["hp"] + 20, p["max_hp"])
        msgs.append(f"⬆️ Уровень {p['level']}! +20 макс. HP.")
    return msgs

def try_rankup(p):
    if not p["faction"]:
        return []
    ranks = FACTIONS[p["faction"]]["ranks"]
    msgs = []
    while p["faction_rank"] < len(ranks) - 1 and p["faction_rep"] >= rep_for_rank(p["faction_rank"] + 1):
        p["faction_rank"] += 1
        msgs.append(f"🎖 Новое звание: {ranks[p['faction_rank']]}!")
    return msgs

def get_rank_name(p):
    if not p["faction"]:
        return "—"
    ranks = FACTIONS[p["faction"]]["ranks"]
    return ranks[min(p["faction_rank"], len(ranks) - 1)]

def is_leader(p):
    if not p["faction"]:
        return False
    ranks = FACTIONS[p["faction"]]["ranks"]
    return p["faction_rank"] >= len(ranks) - 1

def trader_price_modifier(p, base_cost, is_buying):
    # is_buying: True = игрок покупает, False = игрок продаёт
    # Смотрим отношения игрока с текущей локацией (упрощённо — по faction)
    faction = p["faction"]
    sector = SECTORS[p["current_sector"]]
    # Чем хуже отношения игрока с доминирующей фракцией локации — тем хуже цена
    # Упрощённо: штраф/бонус до 30%
    rel_penalty = 0
    for f2, rel in p["diplomacy"].items():
        if rel < -30:
            rel_penalty += 1
    modifier = 1.0 + (rel_penalty * 0.05)
    if is_buying:
        return int(base_cost * modifier)
    else:
        return int(base_cost / modifier * 0.6)

def check_blowout(vk):
    b = get_blowout()
    now = int(time.time())
    # Предупреждение за 5 минут
    if not b["active"] and b["next_ts"] - now <= 300 and b["next_ts"] - now > 295:
        players = get_all_players()
        vids = [p["vk_id"] for p in players]
        notify_players(vk, vids, "⚡️ ВНИМАНИЕ! Через 5 минут начнётся ВЫБРОС. Укройтесь в безопасных секторах!")
    # Начало выброса
    if not b["active"] and now >= b["next_ts"]:
        end_ts = now + 120  # 2 минуты
        set_blowout(b["next_ts"], 1, end_ts)
        players = get_all_players()
        vids = [p["vk_id"] for p in players]
        notify_players(vk, vids, "⚡️ ВЫБРОС НАЧАЛСЯ! Все незащищённые погибнут. Укройтесь немедленно!")
    # Конец выброса
    if b["active"] and now >= b["end_ts"]:
        next_blowout = now + random.randint(900, 2700)
        set_blowout(next_blowout, 0, 0)
        players = get_all_players()
        vids = [p["vk_id"] for p in players]
        notify_players(vk, vids, "✅ Выброс закончился. Можно продолжать движение.")

def apply_blowout_damage(vk, p):
    b = get_blowout()
    if not b["active"]:
        return ""
    if p["faction"] == "Монолит":
        return "⚡️ Выброс активен, но ты невосприимчив (Монолит)."
    sid = p["current_sector"]
    danger = SECTORS[sid]["danger"]
    dmg = danger * 15
    if p["faction"] == "Чистое Небо":
        dmg = dmg // 2
    p["hp"] = max(1, p["hp"] - dmg)
    save_player(p)
    return f"⚡️ Выброс нанёс {dmg} урона! HP: {p['hp']}"

# ═══════════════════════════════════════════════════════════════
# ТУТОРИАЛ
# ═══════════════════════════════════════════════════════════════

TUTORIAL = [
    {
        "text": (
            "☢️ ГОД 2031. УКРАИНА.\n\n"
            "Три года назад произошло то, чего боялись все.\n"
            "Второй взрыв на ЧАЭС — в сотни раз мощнее первого.\n\n"
            "Но это был не взрыв реактора.\n"
            "Это был выброс чего-то неизвестного из недр Зоны.\n\n"
            "Ядерная зима накрыла Европу. Температура упала.\n"
            "В центре Зоны — минус двести. Там не выжить без брони."
        ),
        "btn": "Продолжить"
    },
    {
        "text": (
            "🌡 Чем ближе к центру Зоны — тем холоднее.\n"
            "Чем холоднее — тем опаснее, но тем богаче добыча.\n\n"
            "В Зоне появились АНОМАЛИИ — места, где физика работает иначе.\n"
            "И АРТЕФАКТЫ — застывшая энергия Зоны, дающая силу носителю.\n\n"
            "Ты — сталкер. Одиночка, пришедший в Зону за наживой.\n"
            "Или за правдой. Решай сам."
        ),
        "btn": "Продолжить"
    },
    {
        "text": (
            "🗺 КАРТА ЗОНЫ разделена на ЛОКАЦИИ и СЕКТОРА.\n\n"
            "Локация — большой район (например, Промзона).\n"
            "Сектор — конкретное место внутри локации (Агропром, Свалка...).\n\n"
            "Ты можешь ЗАХВАТЫВАТЬ сектора — это даёт жетоны и ресурсы.\n"
            "Захват занимает 10 минут. Враги могут помешать.\n\n"
            "Жетоны — валюта Зоны. На них покупаешь снаряжение у торговцев."
        ),
        "btn": "Продолжить"
    },
    {
        "text": (
            "⚔️ БОИ — пошаговые.\n\n"
            "На каждом ходу ты выбираешь:\n"
            "• АТАКОВАТЬ — нанести урон врагу\n"
            "• ЛЕЧИТЬСЯ — использовать предмет из инвентаря\n"
            "• ОТСТУПИТЬ — бежать (теряешь 10% жетонов)\n"
            "• СПЕЦПРИЁМ — зависит от фракции и снаряжения\n\n"
            "⚡️ ВЫБРОС — периодическое событие. "
            "Накрывает всю Зону на 2 минуты. "
            "Без укрытия или брони — получишь урон."
        ),
        "btn": "Продолжить"
    },
    {
        "text": (
            "👥 ГРУППИРОВКИ — сердце Зоны.\n\n"
            "Выбери фракцию — получишь уникальные бонусы и врагов.\n"
            "Внутри группировки есть РАНГИ: от рядового до командира.\n"
            "Ранг растёт за квесты и победы над врагами.\n\n"
            "Только командир может объявлять войну и союзы.\n"
            "Отношения между группировками влияют на цены у торговцев.\n\n"
            "Готов выбрать свою сторону?"
        ),
        "btn": "Выбрать группировку"
    },
]

# ═══════════════════════════════════════════════════════════════
# ЭКРАНЫ
# ═══════════════════════════════════════════════════════════════

def screen_main(vk, p):
    stats = calc_stats(p)
    sid = p["current_sector"]
    s = SECTORS[sid]
    loc = s["location"]
    b = get_blowout()
    blowout_line = ""
    now = int(time.time())
    if b["active"]:
        left = max(0, b["end_ts"] - now)
        blowout_line = f"\n⚡️ ВЫБРОС! Осталось ~{left//60}м {left%60}с"
    elif b["next_ts"] - now <= 300:
        blowout_line = f"\n⚠️ Выброс через {(b['next_ts']-now)//60}м!"

    # Захват
    capture_line = ""
    if p["capture_sector"] and p["capture_end"] > now:
        left = p["capture_end"] - now
        capture_line = f"\n🚩 Захват {SECTORS[p['capture_sector']]['name']}: {left//60}м {left%60}с"
    elif p["capture_sector"] and p["capture_end"] <= now and p["capture_end"] > 0:
        # Захват завершён
        csid = p["capture_sector"]
        if csid not in p["controlled_sectors"]:
            p["controlled_sectors"].append(csid)
        p["tokens"] += SECTORS[csid]["tokens"]
        p["capture_sector"] = 0
        p["capture_end"] = 0
        save_player(p)
        capture_line = f"\n✅ Сектор {SECTORS[csid]['name']} захвачен! +{SECTORS[csid]['tokens']} жетонов"

    rank = get_rank_name(p)
    text = (
        f"╔══ ☢️ ЗОНА ══╗\n"
        f"  {p['name']} | {rank}\n"
        f"  {p['faction']}\n"
        f"╠══════════════╣\n"
        f"  ❤️ {p['hp']}/{stats['max_hp']}  💰 {p['tokens']} жт\n"
        f"  ⚔️ {stats['attack']}  🛡 {stats['defense']}  🌡 {stats['warmth']}\n"
        f"╠══════════════╣\n"
        f"  📍 {loc} → {s['name']}\n"
        f"  🌡 {s['temp']}°C  {'☠'*s['danger']}"
        f"{blowout_line}{capture_line}\n"
        f"╚══════════════╝"
    )
    keyboard = kb([
        [("🗺 Карта",        "primary"),   ("🚶 Идти",        "primary")],
        [("⚔️ Бой",          "negative"),  ("🚩 Захват",      "negative")],
        [("🛒 Торговец",     "positive"),  ("🎒 Инвентарь",   "primary")],
        [("🤝 Дипломатия",   "secondary"), ("📋 Задания",     "secondary")],
        [("📋 Личное дело",  "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def screen_personal(vk, p):
    stats = calc_stats(p)
    arts = ", ".join(p["equipped_artifacts"]) or "нет"
    rank = get_rank_name(p)
    next_rank_rep = rep_for_rank(p["faction_rank"] + 1) if p["faction_rank"] < 4 else "—"
    text = (
        f"╔══ 📋 ЛИЧНОЕ ДЕЛО ══╗\n"
        f"  Позывной: {p['name']}\n"
        f"  Группировка: {p['faction']}\n"
        f"  Звание: {rank}\n"
        f"  Репутация: {p['faction_rep']} / {next_rank_rep}\n"
        f"╠══════════════════════╣\n"
        f"  Уровень: {p['level']}\n"
        f"  Опыт: {p['exp']} / {exp_for_next(p['level'])}\n"
        f"  HP: {p['hp']} / {stats['max_hp']}\n"
        f"  Атака: {stats['attack']}\n"
        f"  Защита: {stats['defense']}\n"
        f"  Тепло: {stats['warmth']}\n"
        f"  Жетоны: {p['tokens']}\n"
        f"╠══════════════════════╣\n"
        f"  🔫 {p['weapon']}\n"
        f"  🥼 {p['armor']}\n"
        f"  💎 {arts}\n"
        f"  Секторов: {len(p['controlled_sectors'])}/15\n"
        f"╠══════════════════════╣\n"
        f"  Бонус: {FACTIONS[p['faction']]['bonus']}\n"
        f"╚══════════════════════╝"
    )
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def screen_map(vk, p):
    text = "╔══ 🗺 КАРТА ЗОНЫ ══╗\n"
    for loc_name, loc_data in LOCATIONS.items():
        t_min, t_max = loc_data["temp_range"]
        text += f"\n📍 {loc_name} ({t_min}°C / {t_max}°C)\n"
        for sid in loc_data["sectors"]:
            s = SECTORS[sid]
            owned = "🟢" if sid in p["controlled_sectors"] else ("📍" if sid == p["current_sector"] else "⬜")
            trader = " 🛒" if s["has_trader"] else ""
            text += f"  {owned} {s['name']}{trader} {'☠'*s['danger']}\n"
    text += "╚═══════════════════╝\n🟢=ваш  📍=вы здесь  🛒=торговец"
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def screen_move(vk, p):
    text = "🚶 КУДА ИДТИ?\n────────────────\n"
    btns = []
    for loc_name, loc_data in LOCATIONS.items():
        t_min, t_max = loc_data["temp_range"]
        text += f"\n{loc_name} ({t_min}°C)\n"
        row = []
        for sid in loc_data["sectors"]:
            s = SECTORS[sid]
            mark = "📍" if sid == p["current_sector"] else ("🟢" if sid in p["controlled_sectors"] else "")
            label = f"{mark}{s['name']}"
            row.append((label[:40], "positive" if sid == p["current_sector"] else "secondary"))
        btns.append(row)
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_inventory(vk, p):
    stats = calc_stats(p)
    inv_counts = {}
    for item in p["inventory"]:
        inv_counts[item] = inv_counts.get(item, 0) + 1
    stored_counts = {}
    for item in p["stored_artifacts"]:
        stored_counts[item] = stored_counts.get(item, 0) + 1

    text = (
        f"╔══ 🎒 ИНВЕНТАРЬ ══╗\n"
        f"  🔫 Оружие: {p['weapon']}\n"
        f"     {WEAPONS[p['weapon']]['desc']}\n"
        f"  🥼 Броня: {p['armor']}\n"
        f"     {ARMORS[p['armor']]['desc']}\n"
        f"╠══════════════════╣\n"
        f"  💎 Надето:\n"
    )
    if p["equipped_artifacts"]:
        for a in p["equipped_artifacts"]:
            text += f"    • {a}: {ARTIFACTS[a]['desc']}\n"
    else:
        text += "    нет\n"
    text += "  📦 Склад артефактов:\n"
    if stored_counts:
        for a, cnt in stored_counts.items():
            text += f"    • {a} x{cnt}\n"
    else:
        text += "    пусто\n"
    text += "╠══════════════════╣\n  🧪 Расходники:\n"
    if inv_counts:
        for item, cnt in inv_counts.items():
            c = CONSUMABLES.get(item, {})
            text += f"    • {item} x{cnt}: {c.get('desc','')}\n"
    else:
        text += "    пусто\n"
    text += "╚══════════════════╝"
    btns = [
        [("🔫 Сменить оружие", "primary"), ("🥼 Сменить броню", "primary")],
        [("💎 Надеть арт.", "secondary"),  ("💎 Снять арт.", "secondary")],
        [("🧪 Использовать", "positive")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_trader(vk, p):
    sid = p["current_sector"]
    s = SECTORS[sid]
    if not s["has_trader"]:
        send(vk, p["vk_id"], "🛒 В этом секторе нет торговца.", kb([[("◀️ Назад", "secondary")]]))
        return
    loc = s["location"]
    stock = TRADER_STOCK.get(loc, TRADER_STOCK["Приграничье"])
    rel_mod = 0
    for rel in p["diplomacy"].values():
        if rel < -30:
            rel_mod += 1

    text = f"╔══ 🛒 ТОРГОВЕЦ ══╗\n  {loc}\n"
    if rel_mod > 0:
        text += f"  ⚠️ Плохие отношения: +{rel_mod*5}% к ценам\n"
    text += "╠══════════════════╣\n  🔫 ОРУЖИЕ:\n"
    for wname in stock["weapons"]:
        w = WEAPONS[wname]
        price = trader_price_modifier(p, w["cost"], True)
        text += f"    {wname}: {price}жт | +{w['attack']}⚔️\n    {w['desc']}\n"
    text += "  🥼 БРОНЯ:\n"
    for aname in stock["armors"]:
        a = ARMORS[aname]
        price = trader_price_modifier(p, a["cost"], True)
        text += f"    {aname}: {price}жт | +{a['warmth']}🌡 +{a['defense']}🛡\n    {a['desc']}\n"
    text += "  🧪 ПРЕДМЕТЫ:\n"
    for iname in stock["items"]:
        i = CONSUMABLES[iname]
        price = trader_price_modifier(p, i["cost"], True)
        text += f"    {iname}: {price}жт\n    {i['desc']}\n"
    if "artifacts" in stock:
        text += "  💎 АРТЕФАКТЫ:\n"
        for artname in stock["artifacts"]:
            art = ARTIFACTS[artname]
            price = trader_price_modifier(p, art["cost"], True)
            text += f"    {artname}: {price}жт\n    {art['desc']}\n"
    text += f"╠══════════════════╣\n  💰 Твои жетоны: {p['tokens']}\n╚══════════════════╝"
    btns = [
        [("Купить оружие", "primary"), ("Купить броню", "primary")],
        [("Купить предмет", "positive"), ("Купить арт.", "positive")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_diplomacy(vk, p):
    text = f"╔══ 🤝 ДИПЛОМАТИЯ ══╗\n  {p['faction']}\n╠══════════════════════╣\n"
    for fname, rel in p["diplomacy"].items():
        if rel >= 60:   status = "🟢 Союзник"
        elif rel >= 20: status = "🔵 Дружественно"
        elif rel >= -10:status = "🟡 Нейтрально"
        elif rel >= -40:status = "🟠 Напряжённо"
        else:           status = "🔴 Война"
        text += f"  {fname}: {status} ({rel})\n"
    text += "╚══════════════════════╝"
    btns = []
    if is_leader(p):
        btns.append([("Заключить союз", "positive"), ("Объявить войну", "negative")])
    else:
        text += "\n⚠️ Только командир может менять отношения."
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_quests(vk, p):
    text = "╔══ 📋 ЗАДАНИЯ ══╗\n"
    if p["active_quest"]:
        text += f"  ▶️ Активное: {p['active_quest']}\n  Прогресс: {p['quest_progress']}\n"
    text += f"  ✅ Выполнено: {len(p['completed_quests'])}\n╠══════════════════╣\n"
    if not p["active_quest"]:
        text += "  Задания появляются у NPC\n  в секторах с торговцем.\n"
    text += "╚══════════════════╝"
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

# ═══════════════════════════════════════════════════════════════
# БОЙ (ПОШАГОВЫЙ)
# ═══════════════════════════════════════════════════════════════

def start_battle(vk, p):
    sid = p["current_sector"]
    s = SECTORS[sid]
    danger = min(s["danger"], 6)
    enemy_pool = ENEMIES[danger]
    enemy_name, enemy_hp, enemy_dmg, enemy_exp, enemy_tokens, enemy_desc = random.choice(enemy_pool)
    p["battle_state"] = {
        "enemy_name": enemy_name,
        "enemy_hp": enemy_hp,
        "enemy_hp_max": enemy_hp,
        "enemy_dmg": list(enemy_dmg),
        "enemy_exp": enemy_exp,
        "enemy_tokens": list(enemy_tokens),
        "enemy_desc": enemy_desc,
        "round": 1,
    }
    p["state"] = "battle"
    save_player(p)
    show_battle(vk, p)

def show_battle(vk, p):
    bs = p["battle_state"]
    stats = calc_stats(p)
    hp_bar = "█" * (bs["enemy_hp"] * 10 // bs["enemy_hp_max"]) + "░" * (10 - bs["enemy_hp"] * 10 // bs["enemy_hp_max"])
    text = (
        f"╔══ ⚔️ БОЙ — Раунд {bs['round']} ══╗\n"
        f"  {bs['enemy_name']}\n"
        f"  {bs['enemy_desc']}\n"
        f"  HP: [{hp_bar}] {bs['enemy_hp']}\n"
        f"╠══════════════════════════╣\n"
        f"  Твой HP: {p['hp']}/{stats['max_hp']}\n"
        f"  Атака: {stats['attack']}  Защита: {stats['defense']}\n"
        f"╠══════════════════════════╣\n"
        f"  Выбери действие:\n"
        f"╚══════════════════════════╝"
    )
    has_heal = any(CONSUMABLES.get(i, {}).get("hp_restore", 0) > 0 for i in p["inventory"])
    btns = [
        [("⚔️ Атаковать", "negative"), ("🛡 Защититься", "primary")],
        [("🧪 Лечиться", "positive") if has_heal else ("🧪 Нет лечилок", "secondary"),
         ("🏃 Отступить", "secondary")],
    ]
    # Спецприём для Ренегатов
    if p["faction"] == "Ренегаты":
        btns.insert(1, [("🗡 Диверсия", "primary")])
    send(vk, p["vk_id"], text, kb(btns))

def battle_action(vk, p, action):
    bs = p["battle_state"]
    stats = calc_stats(p)
    log = []
    enemy_alive = True

    if action == "attack":
        dmg = max(1, stats["attack"] + random.randint(-3, 6))
        bs["enemy_hp"] -= dmg
        log.append(f"⚔️ Ты атакуешь: -{dmg} HP врагу.")
        if bs["enemy_hp"] <= 0:
            enemy_alive = False

    elif action == "defend":
        temp_def = stats["defense"] + 15
        e_dmg = max(0, random.randint(*bs["enemy_dmg"]) - temp_def)
        p["hp"] = max(1, p["hp"] - e_dmg)
        log.append(f"🛡 Ты защищаешься. Враг бьёт на {e_dmg} (блок +15).")
        bs["round"] += 1

    elif action == "heal":
        heal_items = [i for i in p["inventory"] if CONSUMABLES.get(i, {}).get("hp_restore", 0) > 0]
        if heal_items:
            item = heal_items[0]
            restore = CONSUMABLES[item]["hp_restore"]
            p["inventory"].remove(item)
            p["hp"] = min(stats["max_hp"], p["hp"] + restore)
            log.append(f"🧪 Использован {item}. +{restore} HP. Теперь {p['hp']}.")
        else:
            log.append("🧪 Нет предметов для лечения.")
        bs["round"] += 1

    elif action == "special" and p["faction"] == "Ренегаты":
        if random.random() < 0.35:
            log.append("🗡 Диверсия! Враг теряет ход.")
            bs["round"] += 1
            p["battle_state"] = bs
            save_player(p)
            result_text = "\n".join(log)
            send(vk, p["vk_id"], result_text, None)
            show_battle(vk, p)
            return
        else:
            log.append("🗡 Диверсия провалилась.")
            bs["round"] += 1

    elif action == "flee":
        penalty = int(p["tokens"] * 0.1)
        p["tokens"] = max(0, p["tokens"] - penalty)
        p["state"] = "main"
        p["battle_state"] = {}
        p["stim_active"] = 0
        save_player(p)
        send(vk, p["vk_id"], f"🏃 Ты отступил. -{penalty} жетонов.", None)
        screen_main(vk, p)
        return

    # Враг атакует (если жив и не defend)
    if enemy_alive and action not in ("defend", "heal", "special"):
        e_dmg = max(0, random.randint(*bs["enemy_dmg"]) - stats["defense"])
        p["hp"] = max(1, p["hp"] - e_dmg)
        log.append(f"🐺 {bs['enemy_name']} атакует: -{e_dmg} HP. Твой HP: {p['hp']}.")
        bs["round"] += 1

    result_text = "\n".join(log)

    if not enemy_alive:
        # Победа
        tokens_gain = random.randint(*bs["enemy_tokens"])
        if p["faction"] == "Бандиты":
            tokens_gain = int(tokens_gain * 1.3)
        exp_gain = bs["enemy_exp"]
        arts_found = []
        sid = p["current_sector"]
        for _ in range(SECTORS[sid]["artifacts"]):
            if random.random() < 0.25:
                arts_found.append(random.choice(list(ARTIFACTS.keys())))

        p["tokens"] += tokens_gain
        p["exp"] += exp_gain
        p["faction_rep"] += 5
        p["stim_active"] = 0

        # Изменение отношений
        for fname, rel in p["diplomacy"].items():
            if fname != p["faction"]:
                p["diplomacy"][fname] = max(-100, p["diplomacy"].get(fname, 0) - 1)

        if arts_found:
            p["stored_artifacts"].extend(arts_found)

        lu = try_levelup(p)
        ru = try_rankup(p)

        p["state"] = "main"
        p["battle_state"] = {}
        save_player(p)

        result_text += (
            f"\n────────────────\n"
            f"✅ ПОБЕДА!\n"
            f"+{tokens_gain} жетонов | +{exp_gain} опыта | +5 репутации\n"
        )
        if arts_found:
            result_text += f"💎 Найдено: {', '.join(arts_found)}\n"
        for m in lu + ru:
            result_text += f"{m}\n"

        send(vk, p["vk_id"], result_text, kb([
            [("⚔️ Ещё враг", "negative"), ("◀️ В лагерь", "secondary")]
        ]))
        return

    if p["hp"] <= 1:
        penalty = int(p["tokens"] * 0.15)
        p["tokens"] = max(0, p["tokens"] - penalty)
        p["hp"] = max(1, stats["max_hp"] // 4)
        p["state"] = "main"
        p["battle_state"] = {}
        p["stim_active"] = 0
        save_player(p)
        result_text += f"\n💔 ПОРАЖЕНИЕ. -{penalty} жетонов. Очнулся с {p['hp']} HP."
        send(vk, p["vk_id"], result_text, kb([[("◀️ В лагерь", "secondary")]]))
        return

    p["battle_state"] = bs
    save_player(p)
    send(vk, p["vk_id"], result_text, None)
    show_battle(vk, p)

# ═══════════════════════════════════════════════════════════════
# ОБРАБОТЧИК СООБЩЕНИЙ
# ═══════════════════════════════════════════════════════════════

def handle_message(vk, vk_id, text):
    text = text.strip()
    check_blowout(vk)
    p = get_player(vk_id)

    if not p:
        create_player(vk_id)
        send(vk, vk_id,
             "☢️ ЗОНА ОТЧУЖДЕНИЯ\n\nДобро пожаловать, сталкер.\nВведи своё имя:",
             kb([[("Начать", "positive")]]))
        return

    state = p["state"]

    # ── Туториал ──
    if state.startswith("tutorial_"):
        step = int(state.split("_")[1])
        if text in ("Начать", "Продолжить", "Выбрать группировку") or step == 0:
            if step < len(TUTORIAL):
                t = TUTORIAL[step]
                p["state"] = f"tutorial_{step + 1}"
                save_player(p)
                send(vk, vk_id, t["text"], kb([[t["btn"]]]))
                return
            else:
                p["state"] = "choose_faction"
                save_player(p)
                screen_choose_faction(vk, p)
                return
        # Ввод имени
        if step == 0 and text != "Начать":
            if len(text.strip()) < 2:
                send(vk, vk_id, "Имя слишком короткое.", None)
                return
            p["name"] = text[:20].strip()
            save_player(p)
        send(vk, vk_id, TUTORIAL[0]["text"], kb([["Продолжить"]]))
        return

    # ── Ввод имени (первый запуск) ──
    if state == "tutorial_0":
        if text == "Начать":
            send(vk, vk_id, "Введи своё позывной, сталкер:", None)
            return
        if len(text.strip()) < 2:
            send(vk, vk_id, "Слишком короткое. Ещё раз:", None)
            return
        p["name"] = text[:20].strip()
        p["state"] = "tutorial_1"
        save_player(p)
        send(vk, vk_id, TUTORIAL[0]["text"], kb([[TUTORIAL[0]["btn"]]]))
        return

    # ── Выбор фракции ──
    if state == "choose_faction":
        if text in FACTIONS:
            screen_faction_info(vk, p, text)
            return
        if text.startswith("✅ Выбрать "):
            fname = text[10:].strip()
            if fname not in FACTIONS:
                ts = p.get("temp_state", "")
                fname = ts.replace("pending:", "") if ts.startswith("pending:") else ""
            if fname in FACTIONS:
                f = FACTIONS[fname]
                p["faction"] = fname
                p["tokens"] = f["start_tokens"]
                p["warmth"] = f["start_warmth"]
                p["weapon"] = "Охотничий нож"
                p["controlled_sectors"] = [1]
                p["diplomacy"] = dict(BASE_RELATIONS[fname])
                p["state"] = "main"
                p["current_sector"] = 1
                save_player(p)
                send(vk, vk_id,
                     f"✅ Группировка: {fname}\n"
                     f"Звание: {FACTIONS[fname]['ranks'][0]}\n"
                     f"База: Кордон (-5°C)\n"
                     f"Жетоны: {f['start_tokens']}\n\n"
                     f"Удачи в Зоне, сталкер.", None)
                screen_main(vk, p)
                return
        if text == "◀️ Другая группировка":
            screen_choose_faction(vk, p)
            return
        screen_choose_faction(vk, p)
        return

    # ── Бой ──
    if state == "battle":
        if text == "⚔️ Атаковать":   battle_action(vk, p, "attack"); return
        if text == "🛡 Защититься":   battle_action(vk, p, "defend"); return
        if text == "🧪 Лечиться":     battle_action(vk, p, "heal"); return
        if text == "🗡 Диверсия":     battle_action(vk, p, "special"); return
        if text == "🏃 Отступить":    battle_action(vk, p, "flee"); return
        show_battle(vk, p)
        return

    # ── Общая навигация ──
    if text in ("◀️ Назад", "◀️ В лагерь"):
        p["temp_state"] = ""
        save_player(p)
        screen_main(vk, p)
        return

    if text == "🗺 Карта":          screen_map(vk, p); return
    if text == "🚶 Идти":           screen_move(vk, p); return
    if text == "📋 Личное дело":    screen_personal(vk, p); return
    if text == "🎒 Инвентарь":      screen_inventory(vk, p); return
    if text == "🛒 Торговец":       screen_trader(vk, p); return
    if text == "🤝 Дипломатия":     screen_diplomacy(vk, p); return
    if text == "📋 Задания":        screen_quests(vk, p); return

    # ── Бой из главного меню ──
    if text in ("⚔️ Бой", "⚔️ Ещё враг"):
        start_battle(vk, p)
        return

    # ── Захват сектора ──
    if text == "🚩 Захват":
        sid = p["current_sector"]
        if sid in p["controlled_sectors"]:
            send(vk, p["vk_id"], "✅ Этот сектор уже ваш.", None)
            screen_main(vk, p)
            return
        if p["capture_sector"]:
            send(vk, p["vk_id"], "⏳ Уже идёт захват другого сектора.", None)
            screen_main(vk, p)
            return
        p["capture_sector"] = sid
        p["capture_end"] = int(time.time()) + 600  # 10 минут
        save_player(p)
        send(vk, p["vk_id"],
             f"🚩 Начат захват: {SECTORS[sid]['name']}\nВремя: 10 минут.\nПродолжай удерживать сектор.",
             kb([[("◀️ Назад", "secondary")]]))
        return

    # ── Движение на карте ──
    for sid, s in SECTORS.items():
        if s["name"] in text:
            b = get_blowout()
            warn = ""
            stats = calc_stats(p)
            needed = sector_min_warmth(sid)
            if needed > stats["warmth"]:
                warn = f"\n⚠️ Опасно: нужно тепло {needed}, у тебя {stats['warmth']}. Продолжить?"
            if b["active"]:
                warn += "\n⚡️ Идёт выброс! Передвижение опасно."
            p["current_sector"] = sid
            p["temp_state"] = ""
            save_player(p)
            msg = f"📍 Ты в секторе: {s['name']}\n{s['location']} | {s['temp']}°C{warn}"
            send(vk, p["vk_id"], msg, None)
            screen_main(vk, p)
            return

    # ── Торговец: подменю покупки ──
    if text == "Купить оружие":
        sid = p["current_sector"]
        loc = SECTORS[sid]["location"]
        stock = TRADER_STOCK.get(loc, TRADER_STOCK["Приграничье"])
        btns = []
        for wname in stock["weapons"]:
            w = WEAPONS[wname]
            price = trader_price_modifier(p, w["cost"], True)
            can = p["tokens"] >= price
            label = f"{'❌' if not can else ''}{wname} {price}жт +{w['attack']}⚔️"
            btns.append([(label[:40], "positive" if can else "secondary")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "buy_weapon"
        save_player(p)
        send(vk, p["vk_id"], "🔫 Выбери оружие:", kb(btns))
        return

    if text == "Купить броню":
        sid = p["current_sector"]
        loc = SECTORS[sid]["location"]
        stock = TRADER_STOCK.get(loc, TRADER_STOCK["Приграничье"])
        btns = []
        for aname in stock["armors"]:
            a = ARMORS[aname]
            price = trader_price_modifier(p, a["cost"], True)
            can = p["tokens"] >= price
            label = f"{'❌' if not can else ''}{aname} {price}жт +{a['warmth']}🌡"
            btns.append([(label[:40], "positive" if can else "secondary")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "buy_armor"
        save_player(p)
        send(vk, p["vk_id"], "🥼 Выбери броню:", kb(btns))
        return

    if text == "Купить предмет":
        sid = p["current_sector"]
        loc = SECTORS[sid]["location"]
        stock = TRADER_STOCK.get(loc, TRADER_STOCK["Приграничье"])
        btns = []
        for iname in stock["items"]:
            i = CONSUMABLES[iname]
            price = trader_price_modifier(p, i["cost"], True)
            can = p["tokens"] >= price
            label = f"{'❌' if not can else ''}{iname} {price}жт"
            btns.append([(label[:40], "positive" if can else "secondary")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "buy_item"
        save_player(p)
        send(vk, p["vk_id"], "🧪 Выбери предмет:", kb(btns))
        return

    if text == "Купить арт.":
        sid = p["current_sector"]
        loc = SECTORS[sid]["location"]
        stock = TRADER_STOCK.get(loc, TRADER_STOCK["Приграничье"])
        if "artifacts" not in stock:
            send(vk, p["vk_id"], "Артефактов нет в наличии.", None)
            screen_trader(vk, p)
            return
        btns = []
        for artname in stock["artifacts"]:
            art = ARTIFACTS[artname]
            price = trader_price_modifier(p, art["cost"], True)
            can = p["tokens"] >= price
            label = f"{'❌' if not can else ''}{artname} {price}жт"
            btns.append([(label[:40], "positive" if can else "secondary")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "buy_artifact"
        save_player(p)
        send(vk, p["vk_id"], "💎 Выбери артефакт:", kb(btns))
        return

    # ── Покупки ──
    ts = p.get("temp_state", "")

    if ts == "buy_weapon":
        for wname, w in WEAPONS.items():
            if wname in text and w["cost"] > 0:
                price = trader_price_modifier(p, w["cost"], True)
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    return
                p["tokens"] -= price
                p["weapon"] = wname
                p["temp_state"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ {wname} куплен. {w['desc']}", None)
                screen_main(vk, p)
                return

    if ts == "buy_armor":
        for aname, a in ARMORS.items():
            if aname in text and a["cost"] > 0:
                price = trader_price_modifier(p, a["cost"], True)
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    return
                p["tokens"] -= price
                p["armor"] = aname
                p["temp_state"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ {aname} куплена. {a['desc']}", None)
                screen_main(vk, p)
                return

    if ts == "buy_item":
        for iname, i in CONSUMABLES.items():
            if iname in text:
                price = trader_price_modifier(p, i["cost"], True)
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    return
                p["tokens"] -= price
                p["inventory"].append(iname)
                if i.get("hp_restore") == 0 and "стим" in iname.lower():
                    p["stim_active"] = 1
                p["temp_state"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ {iname} куплен. {i['desc']}", None)
                screen_main(vk, p)
                return

    if ts == "buy_artifact":
        for artname, art in ARTIFACTS.items():
            if artname in text:
                price = trader_price_modifier(p, art["cost"], True)
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    return
                p["tokens"] -= price
                p["stored_artifacts"].append(artname)
                p["temp_state"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ {artname} куплен. На складе.", None)
                screen_main(vk, p)
                return

    # ── Инвентарь: смена снаряжения ──
    if text == "🔫 Сменить оружие":
        btns = []
        for wname, w in WEAPONS.items():
            if w["cost"] >= 0:
                mark = "✅ " if p["weapon"] == wname else ""
                btns.append([(f"{mark}{wname} +{w['attack']}⚔️"[:40], "positive" if p["weapon"] == wname else "secondary")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "equip_weapon"
        save_player(p)
        send(vk, p["vk_id"], "🔫 Выбери оружие из имеющегося:", kb(btns))
        return

    if text == "🥼 Сменить броню":
        btns = []
        for aname, a in ARMORS.items():
            mark = "✅ " if p["armor"] == aname else ""
            btns.append([(f"{mark}{aname} +{a['warmth']}🌡"[:40], "positive" if p["armor"] == aname else "secondary")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "equip_armor"
        save_player(p)
        send(vk, p["vk_id"], "🥼 Выбери броню из имеющегося:", kb(btns))
        return

    if text == "💎 Надеть арт.":
        if not p["stored_artifacts"]:
            send(vk, p["vk_id"], "Нет артефактов на складе.", None)
            screen_inventory(vk, p)
            return
        seen = []
        btns = []
        for a in p["stored_artifacts"]:
            if a not in seen:
                seen.append(a)
                btns.append([(f"Надеть: {a}"[:40], "positive")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "equip_art"
        save_player(p)
        send(vk, p["vk_id"], "💎 Выбери артефакт:", kb(btns))
        return

    if text == "💎 Снять арт.":
        if not p["equipped_artifacts"]:
            send(vk, p["vk_id"], "Нет надетых артефактов.", None)
            screen_inventory(vk, p)
            return
        btns = [[f"Снять: {a}"[:40]] for a in p["equipped_artifacts"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "unequip_art"
        save_player(p)
        send(vk, p["vk_id"], "💎 Снять артефакт:", kb(btns))
        return

    if text == "🧪 Использовать":
        heal_items = [i for i in p["inventory"] if CONSUMABLES.get(i, {}).get("hp_restore", 0) > 0]
        if not heal_items:
            send(vk, p["vk_id"], "Нет предметов для лечения.", None)
            screen_inventory(vk, p)
            return
        btns = []
        seen = []
        for i in heal_items:
            if i not in seen:
                seen.append(i)
                c = CONSUMABLES[i]
                btns.append([(f"Исп: {i} (+{c['hp_restore']} HP)"[:40], "positive")])
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "use_item"
        save_player(p)
        send(vk, p["vk_id"], "🧪 Что использовать?", kb(btns))
        return

    # Применение смены снаряжения
    if ts == "equip_weapon":
        for wname in WEAPONS:
            if wname in text:
                p["weapon"] = wname
                p["temp_state"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ Оружие: {wname}.", None)
                screen_inventory(vk, p)
                return

    if ts == "equip_armor":
        for aname in ARMORS:
            if aname in text:
                p["armor"] = aname
                p["temp_state"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ Броня: {aname}.", None)
                screen_inventory(vk, p)
                return

    if ts == "equip_art" and text.startswith("Надеть: "):
        aname = text[8:]
        if aname in p["stored_artifacts"]:
            p["stored_artifacts"].remove(aname)
            p["equipped_artifacts"].append(aname)
            p["temp_state"] = ""
            save_player(p)
            send(vk, p["vk_id"], f"✅ {aname} надет.", None)
            screen_inventory(vk, p)
            return

    if ts == "unequip_art" and text.startswith("Снять: "):
        aname = text[7:]
        if aname in p["equipped_artifacts"]:
            p["equipped_artifacts"].remove(aname)
            p["stored_artifacts"].append(aname)
            p["temp_state"] = ""
            save_player(p)
            send(vk, p["vk_id"], f"✅ {aname} снят.", None)
            screen_inventory(vk, p)
            return

    if ts == "use_item" and text.startswith("Исп: "):
        iname = text[5:].split(" (")[0]
        if iname in p["inventory"]:
            c = CONSUMABLES[iname]
            p["inventory"].remove(iname)
            stats = calc_stats(p)
            p["hp"] = min(stats["max_hp"], p["hp"] + c["hp_restore"])
            p["temp_state"] = ""
            save_player(p)
            send(vk, p["vk_id"], f"✅ {iname} использован. HP: {p['hp']}.", None)
            screen_inventory(vk, p)
            return

    # ── Дипломатия ──
    if text == "Заключить союз" and is_leader(p):
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "diplo_ally"
        save_player(p)
        send(vk, p["vk_id"], "🤝 С кем заключить союз?", kb(btns))
        return

    if text == "Объявить войну" and is_leader(p):
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp_state"] = "diplo_war"
        save_player(p)
        send(vk, p["vk_id"], "⚔️ На кого объявить войну?", kb(btns))
        return

    if ts == "diplo_ally" and text in FACTIONS:
        cur = p["diplomacy"].get(text, 0)
        if cur >= 60:
            send(vk, p["vk_id"], f"⚠️ С {text} уже союз.", None)
        else:
            p["diplomacy"][text] = min(100, cur + 30)
            p["temp_state"] = ""
            save_player(p)
            send(vk, p["vk_id"], f"🤝 Союз с {text}. Отношения: {p['diplomacy'][text]}.", None)
        screen_main(vk, p)
        return

    if ts == "diplo_war" and text in FACTIONS:
        cur = p["diplomacy"].get(text, 0)
        if cur < -40:
            send(vk, p["vk_id"], f"⚠️ С {text} уже война.", None)
        else:
            p["diplomacy"][text] = max(-100, cur - 50)
            p["temp_state"] = ""
            save_player(p)
            send(vk, p["vk_id"], f"⚔️ Война с {text}. Отношения: {p['diplomacy'][text]}.", None)
        screen_main(vk, p)
        return

    # ── Смена группировки ──
    if text == "Сменить группировку":
        send(vk, p["vk_id"],
             "⚠️ Смена группировки сбросит звание и репутацию внутри неё. Жетоны и снаряжение сохранятся.",
             kb([[("Подтвердить смену", "negative"), ("◀️ Назад", "secondary")]]))
        p["temp_state"] = "change_faction"
        save_player(p)
        return

    if ts == "change_faction" and text == "Подтвердить смену":
        p["faction"] = ""
        p["faction_rank"] = 0
        p["faction_rep"] = 0
        p["state"] = "choose_faction"
        p["temp_state"] = ""
        save_player(p)
        screen_choose_faction(vk, p)
        return

    # Fallback
    screen_main(vk, p)

def screen_choose_faction(vk, p):
    send(vk, p["vk_id"],
         "☢️ ВЫБОР ГРУППИРОВКИ\n────────────────\nВыбери свою сторону:",
         kb([[name] for name in FACTIONS] + [[("◀️ Назад", "secondary")]]))

def screen_faction_info(vk, p, fname):
    f = FACTIONS[fname]
    text = (
        f"╔══ ☢️ {fname} ══╗\n"
        f"  {f['desc']}\n"
        f"╠════════════════╣\n"
        f"  Бонус: {f['bonus']}\n"
        f"  Жетоны: {f['start_tokens']}\n"
        f"  Тепло: +{f['start_warmth']}\n"
        f"╠════════════════╣\n"
        f"  Звания:\n"
    )
    for i, r in enumerate(f["ranks"]):
        text += f"  {i+1}. {r}\n"
    text += "╚════════════════╝"
    p["temp_state"] = f"pending:{fname}"
    save_player(p)
    send(vk, p["vk_id"], text, kb([
        [(f"✅ Выбрать {fname}"[:40], "positive")],
        [("◀️ Другая группировка", "secondary")],
    ]))

# ═══════════════════════════════════════════════════════════════
# WEBHOOK
# ═══════════════════════════════════════════════════════════════

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
