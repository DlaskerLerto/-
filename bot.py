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
DB_PATH = "zone.db"

# ══════════════════════════════════════════════════════════
#  ИГРОВЫЕ ДАННЫЕ
# ══════════════════════════════════════════════════════════

FACTIONS = {
    "Сталкеры": {
        "desc": "Вольные бродяги. Знают Зону лучше всех.",
        "bonus": "+5 защиты. Разведка: видят соседние сектора.",
        "start_tokens": 150, "start_warmth": 10,
        "attack_bonus": 0, "defense_bonus": 5,
        "ranks": ["Одиночка", "Бродяга", "Сталкер", "Бывалый", "Мастер Зоны"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Долг": {
        "desc": "Военизированная группировка. Дисциплина и огневая мощь.",
        "bonus": "+10 защиты, +5 атаки.",
        "start_tokens": 120, "start_warmth": 15,
        "attack_bonus": 5, "defense_bonus": 10,
        "ranks": ["Рядовой", "Ефрейтор", "Сержант", "Лейтенант", "Полковник"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Свобода": {
        "desc": "Анархисты. Быстрые и дерзкие.",
        "bonus": "+10 атаки. Захват секторов на 20% быстрее.",
        "start_tokens": 130, "start_warmth": 5,
        "attack_bonus": 10, "defense_bonus": 0,
        "ranks": ["Новобранец", "Боец", "Ветеран", "Старший", "Командор"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Бандиты": {
        "desc": "Мародёры. Живут за счёт других.",
        "bonus": "+30% жетонов с добычи, +15 атаки.",
        "start_tokens": 200, "start_warmth": 0,
        "attack_bonus": 15, "defense_bonus": -5,
        "ranks": ["Шестёрка", "Громила", "Авторитет", "Смотрящий", "Пахан"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Военные": {
        "desc": "Армейские части. Тяжёлое снаряжение.",
        "bonus": "+15 защиты, +10 атаки.",
        "start_tokens": 100, "start_warmth": 20,
        "attack_bonus": 10, "defense_bonus": 15,
        "ranks": ["Рядовой", "Младший сержант", "Старшина", "Капитан", "Генерал"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Монолит": {
        "desc": "Фанатики Зоны. Не чувствуют страха.",
        "bonus": "Нет урона от аномалий. +20 атаки.",
        "start_tokens": 80, "start_warmth": 30,
        "attack_bonus": 20, "defense_bonus": 10,
        "ranks": ["Послушник", "Воин", "Страж", "Хранитель", "Пророк"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Наёмники": {
        "desc": "Работают за деньги. Нейтральны.",
        "bonus": "+250 жетонов старт, +10 атаки.",
        "start_tokens": 250, "start_warmth": 10,
        "attack_bonus": 10, "defense_bonus": 5,
        "ranks": ["Стажёр", "Боец", "Специалист", "Эксперт", "Призрак"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Экологи": {
        "desc": "Учёные Зоны. Знатоки артефактов.",
        "bonus": "x2 эффект артефактов.",
        "start_tokens": 120, "start_warmth": 15,
        "attack_bonus": -5, "defense_bonus": 5,
        "ranks": ["Стажёр", "Лаборант", "Исследователь", "Старший учёный", "Профессор"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Ренегаты": {
        "desc": "Дезертиры всех сторон.",
        "bonus": "+15 атаки. Шанс диверсии перед боем.",
        "start_tokens": 140, "start_warmth": 5,
        "attack_bonus": 15, "defense_bonus": -10,
        "ranks": ["Отступник", "Дезертир", "Изгой", "Охотник", "Тень"],
        "rank_rep": [0, 200, 600, 1500, 3500],
    },
    "Чистое Небо": {
        "desc": "Борцы с аномалиями.",
        "bonus": "-50% урона от радиации. +5 атаки, +10 защиты.",
        "start_tokens": 130, "start_warmth": 20,
        "attack_bonus": 5, "defense_bonus": 10,
        "ranks": ["Рекрут", "Разведчик", "Боец", "Офицер", "Командующий"],
        "rank_rep": [0, 200, 600, 1500, 3500],
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

# ── Локации и сектора ────────────────────────────────────

LOCATIONS = {
    1: {
        "name": "Приграничье",
        "temp": -5,
        "desc": "Граница Зоны. Здесь всё началось.",
        "sectors": {
            101: {"name": "КПП «Кордон»",      "type": "base",     "danger": 1, "tokens": 25,  "artifacts": 0},
            102: {"name": "База новичков",       "type": "base",     "danger": 1, "tokens": 20,  "artifacts": 0},
            103: {"name": "Схрон под мостом",    "type": "stash",    "danger": 1, "tokens": 35,  "artifacts": 1},
            104: {"name": "Аномалия «Воронка»",  "type": "anomaly",  "danger": 2, "tokens": 50,  "artifacts": 2},
        },
        "trader_quality": 1,
    },
    2: {
        "name": "Свалка",
        "temp": -18,
        "desc": "Горы ржавого металла. Здесь легко потеряться.",
        "sectors": {
            201: {"name": "Лагерь мародёров",    "type": "enemy",    "danger": 2, "tokens": 45,  "artifacts": 1},
            202: {"name": "Ангар «Росток»",       "type": "base",     "danger": 2, "tokens": 50,  "artifacts": 1},
            203: {"name": "Аномалия «Карусель»",  "type": "anomaly",  "danger": 3, "tokens": 70,  "artifacts": 3},
            204: {"name": "Старый схрон",          "type": "stash",    "danger": 2, "tokens": 55,  "artifacts": 2},
        },
        "trader_quality": 2,
    },
    3: {
        "name": "Тёмная долина",
        "temp": -32,
        "desc": "Туман не рассеивается здесь никогда.",
        "sectors": {
            301: {"name": "Завод «Х-18»",         "type": "dungeon",  "danger": 3, "tokens": 90,  "artifacts": 3},
            302: {"name": "База Свободы",          "type": "base",     "danger": 2, "tokens": 60,  "artifacts": 1},
            303: {"name": "Аномалия «Электра»",   "type": "anomaly",  "danger": 4, "tokens": 110, "artifacts": 4},
            304: {"name": "Схрон в руинах",        "type": "stash",    "danger": 3, "tokens": 80,  "artifacts": 3},
        },
        "trader_quality": 3,
    },
    4: {
        "name": "Агропром",
        "temp": -45,
        "desc": "Заброшенные НИИ. Радиация зашкаливает.",
        "sectors": {
            401: {"name": "Подземные лаборатории","type": "dungeon",  "danger": 4, "tokens": 130, "artifacts": 4},
            402: {"name": "База Военных",          "type": "base",     "danger": 3, "tokens": 80,  "artifacts": 2},
            403: {"name": "Аномалия «Жарка»",      "type": "anomaly",  "danger": 4, "tokens": 140, "artifacts": 5},
            404: {"name": "Тайник учёных",          "type": "stash",    "danger": 3, "tokens": 100, "artifacts": 4},
        },
        "trader_quality": 4,
    },
    5: {
        "name": "Припять",
        "temp": -95,
        "desc": "Мёртвый город. Чем ближе к ЧАЭС — тем холоднее.",
        "sectors": {
            501: {"name": "Площадь Курчатова",    "type": "open",     "danger": 5, "tokens": 200, "artifacts": 5},
            502: {"name": "Гостиница «Полесье»",  "type": "dungeon",  "danger": 5, "tokens": 220, "artifacts": 6},
            503: {"name": "Аномалия «Выжигатель»","type": "anomaly",  "danger": 6, "tokens": 300, "artifacts": 7},
            504: {"name": "Схрон сталкеров",       "type": "stash",    "danger": 5, "tokens": 250, "artifacts": 6},
        },
        "trader_quality": 5,
    },
    6: {
        "name": "Ледяное сердце",
        "temp": -200,
        "desc": "Эпицентр Зоны. −200°C. Без криокостюма — смерть.",
        "sectors": {
            601: {"name": "Саркофаг ЧАЭС",        "type": "dungeon",  "danger": 6, "tokens": 400, "artifacts": 8},
            602: {"name": "Аномалия «Монолит»",   "type": "anomaly",  "danger": 6, "tokens": 500, "artifacts": 9},
            603: {"name": "Схрон Монолита",        "type": "stash",    "danger": 6, "tokens": 450, "artifacts": 8},
        },
        "trader_quality": 0,  # Торговцев нет
    },
}

# Все сектора в плоском виде
def all_sectors():
    result = {}
    for loc_id, loc in LOCATIONS.items():
        for sec_id, sec in loc["sectors"].items():
            result[sec_id] = {**sec, "loc_id": loc_id, "loc_name": loc["name"], "temp": loc["temp"]}
    return result

ALL_SECTORS = all_sectors()

# ── Снаряжение ───────────────────────────────────────────

WEAPONS = {
    "Охотничий нож":  {"attack": 8,   "cost": 0,    "desc": "Надёжный нож выживальщика. Тихо и без лишнего шума.", "special": "backstab"},
    "ПМ":             {"attack": 15,  "cost": 60,   "desc": "Пистолет Макарова. Дёшево и сердито.", "special": "none"},
    "АКС-74У":        {"attack": 30,  "cost": 180,  "desc": "Укороченный автомат. Хорош в ближнем бою.", "special": "burst"},
    "АК-74":          {"attack": 42,  "cost": 300,  "desc": "Классика Зоны. Надёжен в любых условиях.", "special": "burst"},
    "СПАС-12":        {"attack": 55,  "cost": 480,  "desc": "Дробовик. Страшен в упор, бесполезен издали.", "special": "blast"},
    "СВД":            {"attack": 70,  "cost": 650,  "desc": "Снайперская винтовка. Один выстрел — один труп.", "special": "snipe"},
    "РПГ-7":          {"attack": 100, "cost": 1100, "desc": "Гранатомёт. Не оставляет шансов.", "special": "explosive"},
    "Гаусс-пушка":    {"attack": 160, "cost": 2500, "desc": "Экспериментальное оружие. Убивает всё живое.", "special": "gauss"},
}

SPECIAL_NAMES = {
    "backstab":  "🗡 Удар в спину",
    "burst":     "🔥 Очередь",
    "blast":     "💥 Дробь в упор",
    "snipe":     "🎯 Прицельный",
    "explosive": "💣 Подрыв",
    "gauss":     "⚡ Разряд",
    "none":      None,
}

ARMORS = {
    "Нет":               {"defense": 0,  "warmth": 0,   "cost": 0,    "art_slots": 0, "desc": "Никакой защиты. Ты голый в Зоне."},
    "Куртка новичка":    {"defense": 4,  "warmth": 10,  "cost": 50,   "art_slots": 0, "desc": "Базовая экипировка. Чуть лучше, чем ничего."},
    "Бандитский плащ":   {"defense": 6,  "warmth": 15,  "cost": 90,   "art_slots": 0, "desc": "Потрёпанный плащ. Узнаваем в Зоне."},
    "Зимний костюм":     {"defense": 12, "warmth": 30,  "cost": 200,  "art_slots": 1, "desc": "Держит тепло. 1 слот под артефакт."},
    "Комбез сталкера":   {"defense": 18, "warmth": 40,  "cost": 350,  "art_slots": 1, "desc": "Надёжная защита среднего класса. 1 слот."},
    "SEVA-костюм":       {"defense": 28, "warmth": 55,  "cost": 600,  "art_slots": 2, "desc": "Научный костюм. Герметичен. 2 слота."},
    "ЧН-3а":             {"defense": 38, "warmth": 70,  "cost": 900,  "art_slots": 2, "desc": "Костюм Чистого Неба. Проверен в бою. 2 слота."},
    "Экзоскелет-С":      {"defense": 52, "warmth": 85,  "cost": 1500, "art_slots": 3, "desc": "Силовой экзоскелет. Топ среднего класса. 3 слота."},
    "Криокостюм Mk.I":   {"defense": 65, "warmth": 105, "cost": 2800, "art_slots": 3, "desc": "Термозащита первого поколения. 3 слота."},
    "Криокостюм Mk.II":  {"defense": 80, "warmth": 130, "cost": 4500, "art_slots": 4, "desc": "Продвинутая термозащита. 4 слота."},
    "Абсолют":           {"defense": 100,"warmth": 160, "cost": 8000, "art_slots": 4, "desc": "Легендарная броня Зоны. Только для элиты. 4 слота."},
}

ARTIFACTS = {
    "Медуза":       {"hp_bonus": 35,  "attack_bonus": 0,  "defense_bonus": 0,  "warmth_bonus": 0,  "cost": 100,  "desc": "Восстанавливает ткани. Повышает выносливость."},
    "Огненный шар": {"hp_bonus": 0,   "attack_bonus": 18, "defense_bonus": 0,  "warmth_bonus": 8,  "cost": 150,  "desc": "Раскалённый шар. Даёт жар и ярость в бою."},
    "Кристалл":     {"hp_bonus": 0,   "attack_bonus": 0,  "defense_bonus": 12, "warmth_bonus": 12, "cost": 180,  "desc": "Затвердевает при ударе. Отличная пассивная защита."},
    "Морской ёж":   {"hp_bonus": 60,  "attack_bonus": 12, "defense_bonus": 8,  "warmth_bonus": 0,  "cost": 250,  "desc": "Универсальный артефакт. Усиливает всё понемногу."},
    "Пружина":      {"hp_bonus": 0,   "attack_bonus": 30, "defense_bonus": 0,  "warmth_bonus": 0,  "cost": 300,  "desc": "Накапливает кинетическую энергию. Удар — как пушечный выстрел."},
    "Мамины бусы":  {"hp_bonus": 25,  "attack_bonus": 0,  "defense_bonus": 25, "warmth_bonus": 25, "cost": 500,  "desc": "Редкий артефакт. Согревает, защищает, лечит."},
    "Душа":         {"hp_bonus": 120, "attack_bonus": 25, "defense_bonus": 25, "warmth_bonus": 35, "cost": 1000, "desc": "Один из самых редких артефактов Зоны. Мечта сталкера."},
}

MEDKITS = {
    "Бинт":              {"heal": 25,  "cost": 15,  "desc": "Останавливает кровотечение. Хватит ненадолго."},
    "Аптечка":           {"heal": 60,  "cost": 40,  "desc": "Стандартная аптечка. Стабилизирует состояние."},
    "Армейская аптечка": {"heal": 120, "cost": 90,  "desc": "Военный медпакет. Поднимет даже с колен."},
    "Стимулятор":        {"heal": 200, "cost": 180, "desc": "Адреналин и регенерация. Используй в крайнем случае."},
}

# Товары торговцев по качеству локации
TRADER_STOCK = {
    1: {
        "weapons": ["ПМ"],
        "armors": ["Куртка новичка", "Бандитский плащ"],
        "medkits": ["Бинт", "Аптечка"],
        "artifacts": [],
    },
    2: {
        "weapons": ["ПМ", "АКС-74У"],
        "armors": ["Бандитский плащ", "Зимний костюм", "Комбез сталкера"],
        "medkits": ["Бинт", "Аптечка", "Армейская аптечка"],
        "artifacts": ["Медуза"],
    },
    3: {
        "weapons": ["АКС-74У", "АК-74", "СПАС-12"],
        "armors": ["Комбез сталкера", "SEVA-костюм", "ЧН-3а"],
        "medkits": ["Аптечка", "Армейская аптечка", "Стимулятор"],
        "artifacts": ["Медуза", "Огненный шар", "Кристалл"],
    },
    4: {
        "weapons": ["АК-74", "СПАС-12", "СВД"],
        "armors": ["SEVA-костюм", "ЧН-3а", "Экзоскелет-С"],
        "medkits": ["Армейская аптечка", "Стимулятор"],
        "artifacts": ["Огненный шар", "Кристалл", "Морской ёж", "Пружина"],
    },
    5: {
        "weapons": ["СВД", "РПГ-7"],
        "armors": ["Экзоскелет-С", "Криокостюм Mk.I", "Криокостюм Mk.II"],
        "medkits": ["Стимулятор"],
        "artifacts": ["Морской ёж", "Пружина", "Мамины бусы", "Душа"],
    },
}

ENEMIES_BY_DANGER = {
    1: [("Одичавшая собака",  30,  (5, 12),  10,  (8,  18)),
        ("Мародёр",           40,  (7, 15),  15,  (12, 25))],
    2: [("Вооружённый бандит",65,  (12, 22), 25,  (25, 45)),
        ("Зомби",             55,  (8, 18),  20,  (20, 40))],
    3: [("Кровосос",          100, (18, 30), 40,  (45, 80)),
        ("Псевдособака",      80,  (14, 25), 35,  (35, 65))],
    4: [("Контролёр",         140, (22, 38), 60,  (80, 130)),
        ("Псевдогигант",      200, (28, 45), 75,  (100, 160))],
    5: [("Химера",            250, (35, 55), 100, (150, 230)),
        ("Страж Зоны",        320, (42, 65), 120, (180, 280))],
    6: [("Излом",             400, (55, 80), 160, (250, 380)),
        ("Вечный страж",      500, (65, 100),200, (300, 500))],
}

# ══════════════════════════════════════════════════════════
#  БАЗА ДАННЫХ
# ══════════════════════════════════════════════════════════

def init_db():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        vk_id              INTEGER PRIMARY KEY,
        name               TEXT    DEFAULT '__new__',
        state              TEXT    DEFAULT 'tutorial_0',
        faction            TEXT    DEFAULT '',
        faction_rep        INTEGER DEFAULT 0,
        level              INTEGER DEFAULT 1,
        exp                INTEGER DEFAULT 0,
        tokens             INTEGER DEFAULT 50,
        hp                 INTEGER DEFAULT 100,
        max_hp             INTEGER DEFAULT 100,
        weapon             TEXT    DEFAULT 'Охотничий нож',
        armor              TEXT    DEFAULT 'Нет',
        equipped_artifacts TEXT    DEFAULT '[]',
        inventory          TEXT    DEFAULT '{}',
        current_loc        INTEGER DEFAULT 1,
        current_sec        INTEGER DEFAULT 101,
        controlled_sectors TEXT    DEFAULT '[]',
        capture_sector     INTEGER DEFAULT 0,
        capture_end        INTEGER DEFAULT 0,
        diplomacy          TEXT    DEFAULT '{}',
        completed_quests   TEXT    DEFAULT '[]',
        active_quest       TEXT    DEFAULT '',
        quest_progress     INTEGER DEFAULT 0,
        battle_state       TEXT    DEFAULT '',
        temp               TEXT    DEFAULT '',
        last_seen          INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS world (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")
    c.execute("INSERT OR IGNORE INTO world (key,value) VALUES ('blowout_next','0')")
    c.execute("INSERT OR IGNORE INTO world (key,value) VALUES ('blowout_end','0')")
    c.execute("INSERT OR IGNORE INTO world (key,value) VALUES ('faction_relations',?)",
              (json.dumps({f: dict(r) for f, r in BASE_RELATIONS.items()}),))
    con.commit()
    con.close()

def get_world(key):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("SELECT value FROM world WHERE key=?", (key,))
    row = c.fetchone()
    con.close()
    return row[0] if row else None

def set_world(key, value):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("INSERT OR REPLACE INTO world (key,value) VALUES (?,?)", (key, value))
    con.commit()
    con.close()

def get_faction_relations():
    raw = get_world("faction_relations")
    return json.loads(raw) if raw else {f: dict(r) for f, r in BASE_RELATIONS.items()}

def set_faction_relations(rel):
    set_world("faction_relations", json.dumps(rel))

def adjust_faction_relations(faction_a, faction_b, delta):
    rel = get_faction_relations()
    if faction_a in rel and faction_b in rel[faction_a]:
        rel[faction_a][faction_b] = max(-100, min(100, rel[faction_a][faction_b] + delta))
    if faction_b in rel and faction_a in rel[faction_b]:
        rel[faction_b][faction_a] = max(-100, min(100, rel[faction_b][faction_a] + delta))
    set_faction_relations(rel)

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
    for f in ("equipped_artifacts", "inventory", "controlled_sectors",
              "diplomacy", "completed_quests", "battle_state"):
        try:
            p[f] = json.loads(p[f]) if p[f] else ({} if f == "inventory" else [])
        except Exception:
            p[f] = {} if f == "inventory" else []
    return p

def save_player(p):
    data = dict(p)
    for f in ("equipped_artifacts", "inventory", "controlled_sectors",
              "diplomacy", "completed_quests", "battle_state"):
        data[f] = json.dumps(p[f])
    data["last_seen"] = int(time.time())
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    fields = [k for k in data if k != "vk_id"]
    sql = "UPDATE players SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE vk_id=?"
    c.execute(sql, [data[k] for k in fields] + [p["vk_id"]])
    con.commit()
    con.close()

def create_player(vk_id):
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO players (vk_id) VALUES (?)", (vk_id,))
    con.commit()
    con.close()

def get_players_in_sector(sector_id, exclude_vk_id=None):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = con.cursor()
    cutoff = int(time.time()) - 600
    c.execute("SELECT vk_id, name, faction, hp, max_hp FROM players WHERE current_sec=? AND last_seen>? AND state=?",
              (sector_id, cutoff, "main"))
    rows = c.fetchall()
    con.close()
    return [dict(r) for r in rows if r["vk_id"] != exclude_vk_id]

def get_all_players():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = con.cursor()
    c.execute("SELECT vk_id, name, faction, current_sec FROM players WHERE state='main'")
    rows = c.fetchall()
    con.close()
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════════════════
#  VK ХЕЛПЕРЫ
# ══════════════════════════════════════════════════════════

def send(vk, peer_id, text, keyboard=None):
    params = {
        "peer_id": peer_id,
        "message": text[:4096],
        "random_id": get_random_id(),
    }
    if keyboard is not None:
        params["keyboard"] = json.dumps(keyboard)
    try:
        vk.messages.send(**params)
    except Exception as e:
        logging.error(f"send error: {e}")

def notify(vk, vk_id, text):
    """Оповещение без клавиатуры"""
    try:
        vk.messages.send(peer_id=vk_id, message=text[:4096], random_id=get_random_id())
    except Exception as e:
        logging.error(f"notify error: {e}")

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

# ══════════════════════════════════════════════════════════
#  ИГРОВЫЕ ХЕЛПЕРЫ
# ══════════════════════════════════════════════════════════

def calc_stats(p):
    f = FACTIONS.get(p["faction"], {})
    w = WEAPONS.get(p["weapon"], WEAPONS["Охотничий нож"])
    a = ARMORS.get(p["armor"], ARMORS["Нет"])
    attack  = 10 + w["attack"]  + f.get("attack_bonus", 0)
    defense = a["defense"]       + f.get("defense_bonus", 0)
    warmth  = a["warmth"]        + f.get("start_warmth", 0)
    max_hp  = 100 + (p["level"] - 1) * 20
    for art_name in p["equipped_artifacts"]:
        art = ARTIFACTS.get(art_name, {})
        mult = 2 if p["faction"] == "Экологи" else 1
        attack  += art.get("attack_bonus", 0)  * mult
        defense += art.get("defense_bonus", 0) * mult
        warmth  += art.get("warmth_bonus", 0)  * mult
        max_hp  += art.get("hp_bonus", 0)       * mult
    return {"attack": attack, "defense": defense, "warmth": warmth, "max_hp": max_hp}

def get_rank(p):
    f = FACTIONS.get(p["faction"])
    if not f:
        return "—"
    ranks = f["ranks"]
    thresholds = f["rank_rep"]
    rep = p["faction_rep"]
    rank = ranks[0]
    for i, t in enumerate(thresholds):
        if rep >= t:
            rank = ranks[i]
    return rank

def is_commander(p):
    f = FACTIONS.get(p["faction"])
    if not f:
        return False
    return p["faction_rep"] >= f["rank_rep"][-1]

def exp_for_next(level):
    return level * 150

def try_levelup(p):
    msgs = []
    while p["exp"] >= exp_for_next(p["level"]):
        p["exp"] -= exp_for_next(p["level"])
        p["level"] += 1
        p["max_hp"] += 20
        p["hp"] = min(p["hp"] + 20, p["max_hp"])
        msgs.append(f"⬆️ Уровень {p['level']}! +20 макс. HP")
    return msgs

def blowout_active():
    now = int(time.time())
    end = int(get_world("blowout_end") or 0)
    return now < end

def blowout_warning():
    now = int(time.time())
    nxt = int(get_world("blowout_next") or 0)
    return 0 < nxt - now < 120  # предупреждение за 2 минуты

def sector_temp_penalty(p):
    loc = LOCATIONS.get(p["current_loc"], {})
    temp = loc.get("temp", 0)
    stats = calc_stats(p)
    needed = max(0, -temp // 3)
    return max(0, needed - stats["warmth"])

def get_trade_price(item_cost, buyer_faction, seller_faction):
    """Цена с учётом отношений между фракциями"""
    if not buyer_faction or not seller_faction:
        return item_cost
    rel = get_faction_relations()
    relation = rel.get(buyer_faction, {}).get(seller_faction, 0)
    # -100 отношений = +40% цена, +100 = -20% цена
    modifier = 1.0 - (relation / 500.0)
    return max(1, int(item_cost * modifier))

def art_slots_used(p):
    return len(p["equipped_artifacts"])

def art_slots_max(p):
    armor = ARMORS.get(p["armor"], ARMORS["Нет"])
    return armor["art_slots"]

# ══════════════════════════════════════════════════════════
#  ВЫБРОС
# ══════════════════════════════════════════════════════════

def schedule_next_blowout():
    nxt = int(time.time()) + random.randint(1800, 5400)
    set_world("blowout_next", str(nxt))
    set_world("blowout_end", "0")

def start_blowout(vk):
    now = int(time.time())
    end = now + 600  # 10 минут
    set_world("blowout_end", str(end))
    set_world("blowout_next", "0")
    players = get_all_players()
    for pl in players:
        try:
            notify(vk, pl["vk_id"],
                   "⚡️ ВЫБРОС НАЧАЛСЯ!\n"
                   "────────────────\n"
                   "Укройтесь в зданиях или на базах!\n"
                   "Открытые сектора опасны следующие 10 минут.")
        except Exception:
            pass
    schedule_next_blowout_after_end(end)

def schedule_next_blowout_after_end(end_time):
    nxt = end_time + random.randint(1800, 5400)
    set_world("blowout_next", str(nxt))

def check_blowout_trigger(vk):
    now = int(time.time())
    nxt = int(get_world("blowout_next") or 0)
    end = int(get_world("blowout_end") or 0)
    if nxt > 0 and now >= nxt and now > end:
        start_blowout(vk)
    elif nxt > 0 and 0 < nxt - now < 120:
        pass  # предупреждение уже встроено в screen_main

# ══════════════════════════════════════════════════════════
#  УВЕДОМЛЕНИЯ О ЗАХВАТЕ
# ══════════════════════════════════════════════════════════

def notify_sector_attack(vk, attacker, sector_id):
    sec = ALL_SECTORS.get(sector_id, {})
    sec_name = sec.get("name", "?")
    attacker_faction = attacker["faction"]
    players = get_all_players()
    for pl in players:
        if pl["vk_id"] == attacker["vk_id"]:
            continue
        if sector_id in json.loads(
            get_player(pl["vk_id"])["controlled_sectors"]
            if isinstance(get_player(pl["vk_id"])["controlled_sectors"], str)
            else json.dumps(get_player(pl["vk_id"])["controlled_sectors"])
        ):
            try:
                notify(vk, pl["vk_id"],
                       f"⚠️ ТРЕВОГА!\n"
                       f"Ваш сектор «{sec_name}» атакует {attacker['name']} [{attacker_faction}]!")
            except Exception:
                pass

# ══════════════════════════════════════════════════════════
#  ОБУЧЕНИЕ (ТУТОРИАЛ)
# ══════════════════════════════════════════════════════════

TUTORIAL_STEPS = {
    "tutorial_0": {
        "text": (
            "☢️ ЗОНА ОТЧУЖДЕНИЯ. 2031 ГОД.\n"
            "────────────────────────────\n"
            "Три года назад случилось то, чего никто не ожидал.\n\n"
            "Второй взрыв на ЧАЭС был не ядерным — он был другим.\n"
            "Зона расширилась за считанные часы.\n"
            "А потом пришёл холод.\n\n"
            "Учёные называют это «аномальной ядерной зимой».\n"
            "Чем ближе к центру Зоны — тем холоднее.\n"
            "В эпицентре температура достигает −200°C.\n\n"
            "Но люди всё равно идут туда. За артефактами.\n"
            "За правдой. За деньгами. Или просто — потому что\n"
            "им больше некуда идти."
        ),
        "buttons": [[("Дальше →", "positive")]],
        "next": "tutorial_1",
    },
    "tutorial_1": {
        "text": (
            "Ты очнулся у разбитого КПП на границе Зоны.\n"
            "────────────────────────────\n"
            "Рядом — труп военного в разорванной форме.\n"
            "В руке — потрёпанный охотничий нож.\n\n"
            "Кто ты? Откуда? Ты не помнишь.\n"
            "Но ты жив — и это уже кое-что.\n\n"
            "Старый сталкер у костра бросает на тебя взгляд:\n"
            "— Имя? У всех здесь есть имя, даже у мертвецов.\n\n"
            "Как тебя зовут?"
        ),
        "buttons": None,  # Ввод имени
        "next": "tutorial_2",
    },
    "tutorial_2": {
        "text": (
            "— {name}... Редкое имя для этих мест.\n"
            "────────────────────────────\n"
            "Старик кивает и протягивает флягу:\n\n"
            "— Слушай внимательно. Зона — не место для одиночек.\n"
            "Здесь выживают группировками.\n\n"
            "Долг держит периметр. Свобода хочет открыть Зону всем.\n"
            "Бандиты грабят слабых. Военные охраняют секреты.\n"
            "Монолит охраняет центр — и никого туда не пускает.\n\n"
            "— Ты должен примкнуть к кому-то. Или сдохнешь один.\n\n"
            "Выбери группировку:"
        ),
        "buttons": None,  # Выбор фракции
        "next": "tutorial_3",
    },
    "tutorial_3": {
        "text": (
            "Старик кивает на твой выбор.\n"
            "────────────────────────────\n"
            "— Правильно. {faction} — достойные люди.\n\n"
            "Он объясняет правила Зоны:\n\n"
            "📍 Зона делится на ЛОКАЦИИ — большие территории.\n"
            "Внутри каждой — СЕКТОРА: базы, схроны, аномалии.\n\n"
            "⚔️ В секторах водятся мутанты и враги.\n"
            "Победи их — получишь жетоны и опыт.\n\n"
            "🌡 Чем глубже в Зону — тем холоднее.\n"
            "Без тёплой брони далеко не уйдёшь.\n\n"
            "— Твой первый приказ: убей мародёра на КПП."
        ),
        "buttons": [[("Понял. Идём!", "positive")]],
        "next": "tutorial_4",
    },
    "tutorial_4": {
        "text": (
            "Старик останавливает тебя у выхода.\n"
            "────────────────────────────\n"
            "— Подожди. Последнее.\n\n"
            "🏪 ТОРГОВЦЫ продают снаряжение в каждой локации.\n"
            "Чем глубже — тем лучше товар.\n"
            "Отношения с группировками влияют на цены.\n\n"
            "💊 АПТЕЧКИ используй в бою — кнопка «Лечение».\n\n"
            "⚡️ ВЫБРОС случается внезапно.\n"
            "При оповещении — немедленно уходи в здание или на базу.\n\n"
            "— Всё остальное узнаешь сам. Удачи, {name}."
        ),
        "buttons": [[("Начать игру", "positive")]],
        "next": "main",
    },
}

# ══════════════════════════════════════════════════════════
#  ЭКРАНЫ
# ══════════════════════════════════════════════════════════

def screen_main(vk, p):
    stats = calc_stats(p)
    loc = LOCATIONS.get(p["current_loc"], {})
    sec = ALL_SECTORS.get(p["current_sec"], {})
    rank = get_rank(p)
    hp_pct = p["hp"] / max(p["max_hp"], 1)
    hp_bar = "█" * int(hp_pct * 8) + "░" * (8 - int(hp_pct * 8))

    warn = ""
    if blowout_warning():
        nxt = int(get_world("blowout_next") or 0)
        secs = nxt - int(time.time())
        warn = f"\n⚠️ ВЫБРОС через {secs} сек! Укройтесь!"
    elif blowout_active():
        warn = "\n⚡️ ВЫБРОС АКТИВЕН! Открытые сектора опасны!"

    capture_info = ""
    if p["capture_sector"] and p["capture_end"] > int(time.time()):
        remaining = p["capture_end"] - int(time.time())
        cap_sec = ALL_SECTORS.get(p["capture_sector"], {})
        capture_info = f"\n⏳ Захват «{cap_sec.get('name','?')}»: {remaining//60}м {remaining%60}с"

    text = (
        f"┌─ ☢️ ЗОНА ОТЧУЖДЕНИЯ ─────────────────\n"
        f"│ 👤 {p['name']}  [{p['faction']}] {rank}\n"
        f"│ ❤️ {hp_bar} {p['hp']}/{p['max_hp']}\n"
        f"│ 💰 {p['tokens']} жетонов  |  Ур.{p['level']}\n"
        f"│ ⚔️ {stats['attack']}  🛡 {stats['defense']}  🌡 {stats['warmth']}\n"
        f"├──────────────────────────────────────\n"
        f"│ 📍 {loc.get('name','?')}  {loc.get('temp','?')}°C\n"
        f"│ 🔹 Сектор: {sec.get('name','?')}\n"
        f"└──────────────────────────────────────"
        f"{warn}{capture_info}"
    )
    keyboard = kb([
        [("🗺 Карта",         "primary"),  ("⚔️ Бой",         "negative")],
        [("🧭 Торговец",      "positive"), ("🎒 Снаряжение",  "primary")],
        [("🤝 Дипломатия",    "secondary"),("📋 Задания",     "secondary")],
        [("👁 Игроки рядом",  "secondary"),("📂 Личное дело", "secondary")],
    ])
    send(vk, p["vk_id"], text, keyboard)

def screen_map(vk, p):
    text = "🗺 КАРТА ЗОНЫ\n══════════════════════════════\n"
    for loc_id, loc in LOCATIONS.items():
        here = "📍" if loc_id == p["current_loc"] else "  "
        text += f"{here} {loc['name']}  {loc['temp']}°C\n"
        for sec_id, sec in loc["sectors"].items():
            owned = "🟢" if sec_id in p["controlled_sectors"] else "⬜"
            cur = " ◄" if sec_id == p["current_sec"] else ""
            danger_str = "☠" * sec["danger"]
            text += f"    {owned} {sec['name']} [{danger_str}]{cur}\n"
        text += "\n"

    btns = []
    for loc_id, loc in LOCATIONS.items():
        btns.append([(f"→ {loc['name']}", "primary" if loc_id == p["current_loc"] else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_location(vk, p, loc_id):
    loc = LOCATIONS[loc_id]
    stats = calc_stats(p)
    text = (
        f"📍 {loc['name']}  {loc['temp']}°C\n"
        f"══════════════════════════════\n"
        f"{loc['desc']}\n\n"
        f"Сектора:\n"
    )
    btns = []
    for sec_id, sec in loc["sectors"].items():
        owned = "🟢" if sec_id in p["controlled_sectors"] else "⬜"
        cur = " ◄ ВЫ ЗДЕСЬ" if sec_id == p["current_sec"] else ""
        danger_str = "☠" * sec["danger"]
        text += f"  {owned} {sec['name']} [{danger_str}]{cur}\n"
        label = f"{'✅' if sec_id == p['current_sec'] else '→'} {sec['name']}"
        color = "positive" if sec_id == p["current_sec"] else "primary"
        btns.append([(label[:40], color)])

    needed_warmth = max(0, -loc["temp"] // 3)
    if needed_warmth > stats["warmth"]:
        text += f"\n🥶 Предупреждение: нужно тепло {needed_warmth}, у вас {stats['warmth']}.\nВы можете идти, но получите штраф."

    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_equipment(vk, p):
    stats = calc_stats(p)
    a = ARMORS.get(p["armor"], ARMORS["Нет"])
    slots_used = art_slots_used(p)
    slots_max = art_slots_max(p)
    inv = p["inventory"]
    medkit_list = ", ".join(f"{k}×{v}" for k, v in inv.items() if v > 0) or "нет"
    arts_eq = ", ".join(p["equipped_artifacts"]) or "нет"

    text = (
        f"🎒 СНАРЯЖЕНИЕ\n"
        f"══════════════════════════════\n"
        f"🔫 Оружие:  {p['weapon']}\n"
        f"   └ {WEAPONS[p['weapon']]['desc']}\n\n"
        f"🥼 Броня:   {p['armor']}\n"
        f"   └ {a['desc']}\n\n"
        f"💎 Артефакты [{slots_used}/{slots_max} слотов]:\n"
        f"   {arts_eq}\n\n"
        f"💊 Аптечки: {medkit_list}\n"
        f"══════════════════════════════\n"
        f"⚔️ {stats['attack']}  🛡 {stats['defense']}  🌡 {stats['warmth']}  ❤️ {stats['max_hp']}"
    )
    btns = [
        [("🔫 Сменить оружие", "primary"),  ("🥼 Сменить броню",   "primary")],
        [("💎 Надеть артефакт","secondary"), ("💎 Снять артефакт",  "secondary")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_personal_file(vk, p):
    stats = calc_stats(p)
    rank = get_rank(p)
    f = FACTIONS.get(p["faction"], {})
    next_rank_idx = min(len(f.get("ranks", [])) - 1,
                        f.get("ranks", []).index(rank) + 1
                        if rank in f.get("ranks", []) else 0)
    ranks = f.get("ranks", [])
    thresholds = f.get("rank_rep", [0])
    next_rep = thresholds[next_rank_idx] if next_rank_idx < len(thresholds) else "макс."
    sectors_count = len(p["controlled_sectors"])

    text = (
        f"📂 ЛИЧНОЕ ДЕЛО\n"
        f"══════════════════════════════\n"
        f"👤 {p['name']}\n"
        f"🏴 Фракция:   {p['faction']}\n"
        f"🎖 Звание:    {rank}\n"
        f"⭐ Репутация: {p['faction_rep']} / {next_rep}\n"
        f"──────────────────────────────\n"
        f"📊 Уровень:   {p['level']}  (опыт: {p['exp']}/{exp_for_next(p['level'])})\n"
        f"❤️ HP:         {p['hp']} / {p['max_hp']}\n"
        f"⚔️ Атака:     {stats['attack']}\n"
        f"🛡 Защита:    {stats['defense']}\n"
        f"🌡 Тепло:     {stats['warmth']}\n"
        f"💰 Жетоны:    {p['tokens']}\n"
        f"🗺 Секторов:  {sectors_count}\n"
        f"──────────────────────────────\n"
        f"Бонус: {f.get('bonus','—')}"
    )
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

def screen_trader(vk, p):
    loc = LOCATIONS.get(p["current_loc"], {})
    quality = loc.get("trader_quality", 0)
    if quality == 0:
        send(vk, p["vk_id"],
             "🚫 В этой локации нет торговцев.\n«Здесь никто не торгует — слишком опасно.»",
             kb([[("◀️ Назад", "secondary")]]))
        return

    stock = TRADER_STOCK.get(quality, {})
    rel = get_faction_relations()
    trader_faction = "Сталкеры"

    text = (
        f"🧭 ТОРГОВЕЦ\n"
        f"══════════════════════════════\n"
        f"📍 {loc['name']}  |  Жетоны: {p['tokens']}\n\n"
    )
    if stock.get("weapons"):
        text += "🔫 ОРУЖИЕ:\n"
        for name in stock["weapons"]:
            w = WEAPONS[name]
            price = get_trade_price(w["cost"], p["faction"], trader_faction)
            mark = "✅ " if p["weapon"] == name else ""
            text += f"  {mark}{name}: {price}жт  +{w['attack']}⚔️\n  └ {w['desc']}\n"
    if stock.get("armors"):
        text += "\n🥼 БРОНЯ:\n"
        for name in stock["armors"]:
            a = ARMORS[name]
            price = get_trade_price(a["cost"], p["faction"], trader_faction)
            mark = "✅ " if p["armor"] == name else ""
            slots = f"  [{a['art_slots']} слот.]" if a["art_slots"] > 0 else "  [без слотов]"
            text += f"  {mark}{name}: {price}жт  🛡{a['defense']} 🌡{a['warmth']}{slots}\n  └ {a['desc']}\n"
    if stock.get("medkits"):
        text += "\n💊 АПТЕЧКИ:\n"
        for name in stock["medkits"]:
            m = MEDKITS[name]
            price = get_trade_price(m["cost"], p["faction"], trader_faction)
            in_inv = p["inventory"].get(name, 0)
            text += f"  {name}: {price}жт  +{m['heal']}HP  (есть: {in_inv})\n  └ {m['desc']}\n"
    if stock.get("artifacts"):
        text += "\n💎 АРТЕФАКТЫ:\n"
        for name in stock["artifacts"]:
            art = ARTIFACTS[name]
            price = get_trade_price(art["cost"], p["faction"], trader_faction)
            text += f"  {name}: {price}жт\n  └ {art['desc']}\n"

    btns = [
        [("Купить оружие",    "primary"),  ("Купить броню",    "primary")],
        [("Купить аптечку",   "positive"), ("Купить артефакт", "positive")],
        [("◀️ Назад", "secondary")],
    ]
    send(vk, p["vk_id"], text, kb(btns))

def screen_diplomacy(vk, p):
    rel = get_faction_relations()
    text = (
        f"🤝 ДИПЛОМАТИЯ\n"
        f"══════════════════════════════\n"
        f"Твоя фракция: {p['faction']}\n\n"
    )
    our_rels = rel.get(p["faction"], {})
    for fname, val in our_rels.items():
        if val >= 60:
            status = "🟢 Союзник"
        elif val >= 20:
            status = "🔵 Дружелюбно"
        elif val >= -20:
            status = "🟡 Нейтрально"
        elif val >= -50:
            status = "🟠 Напряжённо"
        else:
            status = "🔴 Война"
        text += f"  {fname}: {status} ({val})\n"

    btns = [[("◀️ Назад", "secondary")]]
    if is_commander(p):
        btns.insert(0, [("📢 Объявить союз", "positive"), ("⚔️ Объявить войну", "negative")])
    else:
        text += f"\n⚠️ Управление дипломатией — только для командира фракции."
    send(vk, p["vk_id"], text, kb(btns))

def screen_nearby_players(vk, p):
    players = get_players_in_sector(p["current_sec"], exclude_vk_id=p["vk_id"])
    sec = ALL_SECTORS.get(p["current_sec"], {})
    text = f"👁 ИГРОКИ В СЕКТОРЕ «{sec.get('name','?')}»\n══════════════════════════════\n"
    if not players:
        text += "Никого нет."
    else:
        for pl in players:
            hp_pct = int((pl["hp"] / max(pl["max_hp"], 1)) * 10)
            text += f"  👤 {pl['name']} [{pl['faction']}]  ❤️{'█'*hp_pct}{'░'*(10-hp_pct)}\n"
    btns = []
    for pl in players:
        btns.append([(f"⚔️ Атаковать {pl['name']}", "negative")])
        btns.append([(f"🤝 Торговать с {pl['name']}", "positive")])
    btns.append([("◀️ Назад", "secondary")])
    send(vk, p["vk_id"], text, kb(btns))

def screen_quests(vk, p):
    text = (
        f"📋 ЗАДАНИЯ\n"
        f"══════════════════════════════\n"
    )
    if p["active_quest"]:
        text += f"▶️ Активное: {p['active_quest']}\nПрогресс: {p['quest_progress']}\n\n"
    text += f"✅ Выполнено: {len(p['completed_quests'])}\n\nЗадания появляются у торговцев."
    send(vk, p["vk_id"], text, kb([[("◀️ Назад", "secondary")]]))

# ══════════════════════════════════════════════════════════
#  БОЙ (ПОШАГОВЫЙ)
# ══════════════════════════════════════════════════════════

def start_battle(vk, p, enemy_data=None):
    sec = ALL_SECTORS.get(p["current_sec"], {})
    danger = sec.get("danger", 1)
    if enemy_data is None:
        pool = ENEMIES_BY_DANGER.get(min(danger, 6), ENEMIES_BY_DANGER[1])
        name, hp, dmg_range, exp_gain, tokens_range = random.choice(pool)
        enemy_data = {
            "name": name, "hp": hp, "max_hp": hp,
            "dmg_range": list(dmg_range),
            "exp": exp_gain, "tokens": list(tokens_range),
        }

    p["battle_state"] = {
        "enemy": enemy_data,
        "round": 1,
        "stunned": False,
    }
    p["state"] = "battle"
    save_player(p)

    stats = calc_stats(p)
    penalty = sector_temp_penalty(p)
    loc = LOCATIONS.get(p["current_loc"], {})
    text = (
        f"⚔️ ВСТРЕЧА!\n"
        f"══════════════════════════════\n"
        f"📍 {loc.get('name','?')} — {sec.get('name','?')}\n\n"
        f"Перед тобой: {enemy_data['name']}\n"
        f"❤️ Враг: {enemy_data['hp']}/{enemy_data['max_hp']}\n\n"
        f"Твой HP: {p['hp']}/{p['max_hp']}\n"
        f"Атака: {stats['attack']}  Защита: {stats['defense']}"
    )
    if penalty > 0:
        text += f"\n🥶 Штраф холода: −{penalty}"
    _send_battle_buttons(vk, p, text)

def _send_battle_buttons(vk, p, text):
    w = WEAPONS.get(p["weapon"], {})
    special = w.get("special", "none")
    special_name = SPECIAL_NAMES.get(special)
    inv = p["inventory"]
    has_medkit = any(v > 0 for v in inv.values())

    btns = [
        [("🗡 Атака", "negative"), ("💥 Сильный удар", "negative")],
    ]
    row2 = []
    if has_medkit:
        row2.append(("💊 Лечение", "positive"))
    row2.append(("🏃 Отступить", "secondary"))
    btns.append(row2)
    if special_name:
        btns.append([(special_name, "primary")])
    send(vk, p["vk_id"], text, kb(btns))

def process_battle_action(vk, p, action):
    bs = p["battle_state"]
    enemy = bs["enemy"]
    stats = calc_stats(p)
    penalty = sector_temp_penalty(p)
    eff_attack = max(1, stats["attack"] - penalty)
    eff_defense = max(0, stats["defense"] - penalty // 2)

    result_lines = [f"⚔️ Раунд {bs['round']}\n══════════════════════════════"]

    # ── Действие игрока ──
    if action == "attack":
        dmg = max(1, eff_attack + random.randint(-3, 5))
        enemy["hp"] -= dmg
        result_lines.append(f"🗡 Ты атакуешь: -{dmg} HP врагу")

    elif action == "heavy":
        dmg = max(1, int(eff_attack * 1.7) + random.randint(-5, 5))
        miss_chance = 0.25
        if random.random() < miss_chance:
            result_lines.append("💨 Сильный удар — промах!")
        else:
            enemy["hp"] -= dmg
            result_lines.append(f"💥 Сильный удар: -{dmg} HP врагу")

    elif action == "heal":
        inv = p["inventory"]
        healed = False
        for mname in ["Стимулятор", "Армейская аптечка", "Аптечка", "Бинт"]:
            if inv.get(mname, 0) > 0:
                heal_val = MEDKITS[mname]["heal"]
                p["hp"] = min(p["max_hp"], p["hp"] + heal_val)
                inv[mname] -= 1
                result_lines.append(f"💊 {mname}: +{heal_val} HP → {p['hp']}/{p['max_hp']}")
                healed = True
                break
        if not healed:
            result_lines.append("💊 Нет аптечек!")

    elif action == "flee":
        flee_chance = 0.6
        if bs.get("stunned"):
            flee_chance = 0.3
        if random.random() < flee_chance:
            p["state"] = "main"
            p["battle_state"] = []
            save_player(p)
            send(vk, p["vk_id"], "🏃 Ты отступил в темноту...", None)
            screen_main(vk, p)
            return
        else:
            result_lines.append("❌ Не удалось убежать!")

    elif action == "special":
        w = WEAPONS.get(p["weapon"], {})
        special = w.get("special", "none")
        dmg = eff_attack
        if special == "backstab":
            dmg = int(eff_attack * 2.5)
            result_lines.append(f"🗡 Удар в спину: -{dmg} HP")
        elif special in ("burst", "blast"):
            dmg = int(eff_attack * 1.4)
            result_lines.append(f"🔥 Очередь/дробь: -{dmg} HP")
        elif special == "snipe":
            dmg = int(eff_attack * 2.0)
            result_lines.append(f"🎯 Прицельный: -{dmg} HP")
        elif special == "explosive":
            dmg = int(eff_attack * 2.2)
            result_lines.append(f"💣 Взрыв: -{dmg} HP")
        elif special == "gauss":
            dmg = int(eff_attack * 3.0)
            result_lines.append(f"⚡ Разряд: -{dmg} HP")
        else:
            dmg = eff_attack
            result_lines.append(f"⚔️ Особый удар: -{dmg} HP")
        enemy["hp"] -= dmg

    # ── Проверка смерти врага ──
    if enemy["hp"] <= 0:
        tokens_gain = random.randint(*enemy["tokens"])
        if p["faction"] == "Бандиты":
            tokens_gain = int(tokens_gain * 1.3)
        exp_gain = enemy["exp"]
        p["tokens"] += tokens_gain
        p["exp"] += exp_gain
        p["faction_rep"] += 5
        p["state"] = "main"
        p["battle_state"] = []

        arts_found = []
        sec = ALL_SECTORS.get(p["current_sec"], {})
        for _ in range(sec.get("artifacts", 0)):
            if random.random() < 0.2:
                arts_found.append(random.choice(list(ARTIFACTS.keys())))
        for a in arts_found:
            p["inventory"][a] = p["inventory"].get(a, 0) + 1

        lu = try_levelup(p)

        # Влияем на отношения фракций
        # Убийство врага враждебной фракции улучшает отношения со своей
        # Убийство члена нейтральной фракции — небольшой штраф (в PvP)
        save_player(p)

        result_lines.append(f"\n✅ {enemy['name']} уничтожен!")
        result_lines.append(f"+{tokens_gain} жетонов  +{exp_gain} опыта  +5 репутации")
        if arts_found:
            result_lines.append(f"💎 Найдено: {', '.join(arts_found)}")
        for m in lu:
            result_lines.append(m)

        text = "\n".join(result_lines)
        send(vk, p["vk_id"], text,
             kb([[("⚔️ Ещё раз", "negative"), ("◀️ В лагерь", "secondary")]]))
        return

    # ── Ход врага ──
    bs["round"] += 1
    enemy_dmg = max(0, random.randint(*enemy["dmg_range"]) - eff_defense)

    # Шанс оглушения
    if random.random() < 0.1:
        bs["stunned"] = True
        result_lines.append(f"😵 {enemy['name']} оглушает тебя!")
    else:
        bs["stunned"] = False

    p["hp"] -= enemy_dmg
    result_lines.append(f"\n{enemy['name']} атакует: -{enemy_dmg} HP")
    result_lines.append(f"Твой HP: {p['hp']}/{p['max_hp']}  |  Враг: {enemy['hp']}/{enemy['max_hp']}")

    # ── Смерть игрока ──
    if p["hp"] <= 0:
        p["hp"] = max(1, p["max_hp"] // 5)
        penalty_tokens = int(p["tokens"] * 0.15)
        p["tokens"] = max(0, p["tokens"] - penalty_tokens)
        p["state"] = "main"
        p["battle_state"] = []
        save_player(p)
        result_lines.append(f"\n💀 Ты упал...")
        result_lines.append(f"Очнулся у костра. HP: {p['hp']}. Потеряно {penalty_tokens} жетонов.")
        text = "\n".join(result_lines)
        send(vk, p["vk_id"], text, kb([[("◀️ В лагерь", "secondary")]]))
        return

    p["battle_state"] = bs
    save_player(p)
    text = "\n".join(result_lines)
    _send_battle_buttons(vk, p, text)

# ══════════════════════════════════════════════════════════
#  ПОКУПКИ
# ══════════════════════════════════════════════════════════

def screen_buy_weapons(vk, p):
    loc = LOCATIONS.get(p["current_loc"], {})
    quality = loc.get("trader_quality", 0)
    stock = TRADER_STOCK.get(quality, {}).get("weapons", [])
    if not stock:
        send(vk, p["vk_id"], "Оружия нет в продаже.", None)
        screen_trader(vk, p)
        return
    btns = []
    for name in stock:
        w = WEAPONS[name]
        price = get_trade_price(w["cost"], p["faction"], "Сталкеры")
        can = p["tokens"] >= price
        mark = "✅ " if p["weapon"] == name else ("" if can else "❌ ")
        label = f"{mark}{name} ({price}жт)"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    p["temp"] = "buy_weapon"
    save_player(p)
    send(vk, p["vk_id"], "🔫 Выбери оружие:", kb(btns))

def screen_buy_armors(vk, p):
    loc = LOCATIONS.get(p["current_loc"], {})
    quality = loc.get("trader_quality", 0)
    stock = TRADER_STOCK.get(quality, {}).get("armors", [])
    if not stock:
        send(vk, p["vk_id"], "Брони нет в продаже.", None)
        screen_trader(vk, p)
        return
    btns = []
    for name in stock:
        a = ARMORS[name]
        price = get_trade_price(a["cost"], p["faction"], "Сталкеры")
        can = p["tokens"] >= price
        mark = "✅ " if p["armor"] == name else ("" if can else "❌ ")
        label = f"{mark}{name} ({price}жт) [{a['art_slots']}сл.]"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    p["temp"] = "buy_armor"
    save_player(p)
    send(vk, p["vk_id"], "🥼 Выбери броню:", kb(btns))

def screen_buy_medkits(vk, p):
    loc = LOCATIONS.get(p["current_loc"], {})
    quality = loc.get("trader_quality", 0)
    stock = TRADER_STOCK.get(quality, {}).get("medkits", [])
    btns = []
    for name in stock:
        m = MEDKITS[name]
        price = get_trade_price(m["cost"], p["faction"], "Сталкеры")
        can = p["tokens"] >= price
        in_inv = p["inventory"].get(name, 0)
        label = f"{'❌ ' if not can else ''}{name} ({price}жт) ×{in_inv}"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    p["temp"] = "buy_medkit"
    save_player(p)
    send(vk, p["vk_id"], "💊 Выбери аптечку:", kb(btns))

def screen_buy_artifacts(vk, p):
    loc = LOCATIONS.get(p["current_loc"], {})
    quality = loc.get("trader_quality", 0)
    stock = TRADER_STOCK.get(quality, {}).get("artifacts", [])
    if not stock:
        send(vk, p["vk_id"], "Артефактов нет в продаже.", None)
        screen_trader(vk, p)
        return
    slots_max = art_slots_max(p)
    slots_used = art_slots_used(p)
    btns = []
    for name in stock:
        art = ARTIFACTS[name]
        price = get_trade_price(art["cost"], p["faction"], "Сталкеры")
        can = p["tokens"] >= price
        label = f"{'❌ ' if not can else ''}{name} ({price}жт)"
        btns.append([(label[:40], "positive" if can else "secondary")])
    btns.append([("◀️ Назад", "secondary")])
    p["temp"] = "buy_artifact"
    save_player(p)
    info = f"💎 Слотов под артефакты: {slots_used}/{slots_max}\nВыбери артефакт:"
    send(vk, p["vk_id"], info, kb(btns))

# ══════════════════════════════════════════════════════════
#  ТУТОРИАЛ
# ══════════════════════════════════════════════════════════

def handle_tutorial(vk, p, text):
    state = p["state"]
    step = TUTORIAL_STEPS.get(state)
    if not step:
        p["state"] = "main"
        save_player(p)
        screen_main(vk, p)
        return

    # tutorial_1 — ввод имени
    if state == "tutorial_1":
        if text == "Начать":
            send(vk, p["vk_id"], step["text"], None)
            return
        if len(text.strip()) < 2:
            send(vk, p["vk_id"], "Имя слишком короткое. Попробуй ещё раз.", None)
            return
        p["name"] = text[:20].strip()
        p["state"] = "tutorial_2"
        save_player(p)
        next_step = TUTORIAL_STEPS["tutorial_2"]
        msg = next_step["text"].replace("{name}", p["name"])
        send(vk, p["vk_id"], msg, kb([[fname] for fname in FACTIONS]))
        return

    # tutorial_2 — выбор фракции (просмотр)
    if state == "tutorial_2":
        if text in FACTIONS:
            f = FACTIONS[text]
            msg = (
                f"☢️ {text}\n{f['desc']}\n\n"
                f"Бонус: {f['bonus']}\n"
                f"Стартовые жетоны: {f['start_tokens']}"
            )
            p["temp"] = f"pending_faction:{text}"
            save_player(p)
            send(vk, p["vk_id"], msg,
                 kb([[(f"✅ Выбрать {text}"[:40], "positive")],
                     [("◀️ Другая фракция", "secondary")]]))
            return
        if text.startswith("✅ Выбрать "):
            fname = text[10:].strip()
            if fname not in FACTIONS:
                fname = p["temp"].replace("pending_faction:", "") if p["temp"].startswith("pending_faction:") else ""
            if fname in FACTIONS:
                fdata = FACTIONS[fname]
                p["faction"] = fname
                p["tokens"] = fdata["start_tokens"]
                p["diplomacy"] = dict(BASE_RELATIONS[fname])
                p["state"] = "tutorial_3"
                save_player(p)
                next_step = TUTORIAL_STEPS["tutorial_3"]
                msg = next_step["text"].replace("{faction}", fname)
                send(vk, p["vk_id"], msg, kb(next_step["buttons"]))
                return
        if text == "◀️ Другая фракция":
            step2 = TUTORIAL_STEPS["tutorial_2"]
            msg = step2["text"].replace("{name}", p["name"])
            send(vk, p["vk_id"], msg, kb([[fname] for fname in FACTIONS]))
            return
        return

    # Остальные шаги туториала — кнопка "Дальше"
    if text in ("Дальше →", "Начать игру", "Понял. Идём!"):
        next_state = step["next"]
        if next_state == "main":
            p["state"] = "main"
            p["current_loc"] = 1
            p["current_sec"] = 101
            p["controlled_sectors"] = []
            p["blowout_next"] = int(time.time()) + 1800
            # Первое задание
            p["active_quest"] = "Убить мародёра на КПП «Кордон»"
            p["quest_progress"] = 0
            save_player(p)
            send(vk, p["vk_id"],
                 f"⚡️ Добро пожаловать в Зону, {p['name']}!\n"
                 f"Ты в секторе «КПП «Кордон»».\n"
                 f"Первое задание: убей мародёра.", None)
            screen_main(vk, p)
        else:
            p["state"] = next_state
            save_player(p)
            next_step = TUTORIAL_STEPS[next_state]
            msg = next_step["text"].replace("{name}", p.get("name","")).replace("{faction}", p.get("faction",""))
            buttons = next_step.get("buttons") or [[("Начать →", "positive")]]
            send(vk, p["vk_id"], msg, kb(buttons))
        return

    # Ввод имени при первом запуске
    if state == "tutorial_0":
        if text == "Начать":
            p["state"] = "tutorial_1"
            save_player(p)
            step1 = TUTORIAL_STEPS["tutorial_1"]
            send(vk, p["vk_id"], step1["text"], None)
        return

# ══════════════════════════════════════════════════════════
#  ГЛАВНЫЙ ОБРАБОТЧИК
# ══════════════════════════════════════════════════════════

def handle_message(vk, vk_id, text):
    text = text.strip()
    check_blowout_trigger(vk)

    p = get_player(vk_id)
    if not p:
        create_player(vk_id)
        p = get_player(vk_id)
        step0 = TUTORIAL_STEPS["tutorial_0"]
        send(vk, vk_id, step0["text"], kb(step0["buttons"]))
        return

    state = p["state"]

    # ── Туториал ──
    if state.startswith("tutorial"):
        handle_tutorial(vk, p, text)
        return

    # ── Бой ──
    if state == "battle":
        if text == "🗡 Атака":
            process_battle_action(vk, p, "attack")
        elif text == "💥 Сильный удар":
            process_battle_action(vk, p, "heavy")
        elif text == "💊 Лечение":
            process_battle_action(vk, p, "heal")
        elif text == "🏃 Отступить":
            process_battle_action(vk, p, "flee")
        elif text in (SPECIAL_NAMES.get(WEAPONS.get(p["weapon"], {}).get("special"), ""),):
            process_battle_action(vk, p, "special")
        elif any(text == v for v in SPECIAL_NAMES.values() if v):
            process_battle_action(vk, p, "special")
        else:
            bs = p["battle_state"]
            enemy = bs["enemy"] if bs else {}
            send(vk, p["vk_id"],
                 f"⚔️ Бой продолжается!\n{enemy.get('name','?')}: {enemy.get('hp','?')} HP",
                 None)
            _send_battle_buttons(vk, p, "")
        return

    # ── Навигация ──
    if text in ("◀️ Назад", "◀️ В лагерь"):
        p["temp"] = ""
        save_player(p)
        screen_main(vk, p)
        return

    # ── Главное меню ──
    nav = {
        "🗺 Карта":        lambda: screen_map(vk, p),
        "🧭 Торговец":     lambda: screen_trader(vk, p),
        "🎒 Снаряжение":   lambda: screen_equipment(vk, p),
        "🤝 Дипломатия":   lambda: screen_diplomacy(vk, p),
        "📋 Задания":      lambda: screen_quests(vk, p),
        "📂 Личное дело":  lambda: screen_personal_file(vk, p),
        "👁 Игроки рядом": lambda: screen_nearby_players(vk, p),
    }
    if text in nav:
        nav[text]()
        return

    # ── Бой с мобом ──
    if text == "⚔️ Бой":
        sec = ALL_SECTORS.get(p["current_sec"], {})
        danger = sec.get("danger", 1)
        # Предупреждение об опасности
        stats = calc_stats(p)
        penalty = sector_temp_penalty(p)
        if penalty > stats["defense"]:
            send(vk, p["vk_id"],
                 f"⚠️ Опасное место! Холод сведёт твою защиту к нулю.\n"
                 f"Штраф: -{penalty}. Идти на свой страх и риск?",
                 kb([[("⚔️ Рискнуть!", "negative"), ("◀️ Назад", "secondary")]]))
            p["temp"] = "confirm_dangerous_battle"
            save_player(p)
            return
        start_battle(vk, p)
        return

    if text == "⚔️ Рискнуть!":
        start_battle(vk, p)
        return

    if text == "⚔️ Ещё раз":
        start_battle(vk, p)
        return

    # ── Переход на локацию ──
    for loc_id, loc in LOCATIONS.items():
        if text == f"→ {loc['name']}":
            screen_location(vk, p, loc_id)
            return

    # ── Переход в сектор ──
    for sec_id, sec in ALL_SECTORS.items():
        if text in (f"→ {sec['name']}", f"✅ {sec['name']}"):
            p["current_loc"] = sec["loc_id"]
            p["current_sec"] = sec_id
            save_player(p)
            loc = LOCATIONS[sec["loc_id"]]
            stats = calc_stats(p)
            needed = max(0, -loc["temp"] // 3)
            msg = f"📍 Ты в секторе «{sec['name']}»\n{loc['name']} | {loc['temp']}°C"
            if needed > stats["warmth"]:
                msg += f"\n🥶 Холодно! Нужно тепло {needed}, у тебя {stats['warmth']}."
            send(vk, p["vk_id"], msg, None)
            screen_main(vk, p)
            return

    # ── Снаряжение ──
    if text == "🔫 Сменить оружие":
        screen_buy_weapons(vk, p); return
    if text == "🥼 Сменить броню":
        screen_buy_armors(vk, p); return
    if text == "💎 Надеть артефакт":
        _screen_equip_art(vk, p); return
    if text == "💎 Снять артефакт":
        _screen_unequip_art(vk, p); return

    # ── Магазин ──
    if text == "Купить оружие":
        screen_buy_weapons(vk, p); return
    if text == "Купить броню":
        screen_buy_armors(vk, p); return
    if text == "Купить аптечку":
        screen_buy_medkits(vk, p); return
    if text == "Купить артефакт":
        screen_buy_artifacts(vk, p); return

    # ── Обработка покупок ──
    temp = p.get("temp", "")

    if temp == "buy_weapon":
        for name, w in WEAPONS.items():
            if name in text and w["cost"] > 0:
                price = get_trade_price(w["cost"], p["faction"], "Сталкеры")
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    screen_buy_weapons(vk, p)
                    return
                p["tokens"] -= price
                p["weapon"] = name
                p["temp"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ Оружие: {name}\n{w['desc']}", None)
                screen_equipment(vk, p)
                return

    if temp == "buy_armor":
        for name, a in ARMORS.items():
            if name in text and a["cost"] > 0:
                price = get_trade_price(a["cost"], p["faction"], "Сталкеры")
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    screen_buy_armors(vk, p)
                    return
                # При смене брони снимаем артефакты если слотов не хватает
                new_slots = a["art_slots"]
                while len(p["equipped_artifacts"]) > new_slots:
                    removed = p["equipped_artifacts"].pop()
                    p["inventory"][removed] = p["inventory"].get(removed, 0) + 1
                p["tokens"] -= price
                p["armor"] = name
                p["temp"] = ""
                save_player(p)
                msg = f"✅ Броня: {name}\n{a['desc']}\nСлотов под артефакты: {new_slots}"
                if new_slots < art_slots_used(p):
                    msg += "\nАртефакты сняты из-за нехватки слотов."
                send(vk, p["vk_id"], msg, None)
                screen_equipment(vk, p)
                return

    if temp == "buy_medkit":
        for name, m in MEDKITS.items():
            if name in text:
                price = get_trade_price(m["cost"], p["faction"], "Сталкеры")
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    screen_buy_medkits(vk, p)
                    return
                p["tokens"] -= price
                p["inventory"][name] = p["inventory"].get(name, 0) + 1
                p["temp"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ Куплено: {name}. В рюкзаке: ×{p['inventory'][name]}", None)
                screen_trader(vk, p)
                return

    if temp == "buy_artifact":
        for name, art in ARTIFACTS.items():
            if name in text:
                price = get_trade_price(art["cost"], p["faction"], "Сталкеры")
                if p["tokens"] < price:
                    send(vk, p["vk_id"], f"Не хватает жетонов. Нужно {price}.", None)
                    screen_buy_artifacts(vk, p)
                    return
                p["tokens"] -= price
                p["inventory"][name] = p["inventory"].get(name, 0) + 1
                p["temp"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ Куплен: {name}\n{art['desc']}", None)
                screen_equipment(vk, p)
                return

    if temp == "equip_art":
        for name in list(ARTIFACTS.keys()):
            if f"Надеть: {name}" == text:
                if p["inventory"].get(name, 0) <= 0:
                    send(vk, p["vk_id"], "Нет на складе.", None)
                    return
                if art_slots_used(p) >= art_slots_max(p):
                    send(vk, p["vk_id"],
                         f"Все слоты заняты ({art_slots_max(p)}/{art_slots_max(p)}).\nСначала сними артефакт.", None)
                    return
                p["inventory"][name] -= 1
                p["equipped_artifacts"].append(name)
                p["temp"] = ""
                save_player(p)
                send(vk, p["vk_id"], f"✅ {name} надет.\n{ARTIFACTS[name]['desc']}", None)
                screen_equipment(vk, p)
                return

    if temp == "unequip_art":
        for name in list(ARTIFACTS.keys()):
            if f"Снять: {name}" == text:
                if name in p["equipped_artifacts"]:
                    p["equipped_artifacts"].remove(name)
                    p["inventory"][name] = p["inventory"].get(name, 0) + 1
                    p["temp"] = ""
                    save_player(p)
                    send(vk, p["vk_id"], f"✅ {name} снят, лежит на складе.", None)
                    screen_equipment(vk, p)
                    return

    # ── Дипломатия (только командир) ──
    if text == "📢 Объявить союз" and is_commander(p):
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp"] = "diplo_ally"
        save_player(p)
        send(vk, p["vk_id"], "🤝 С кем заключить союз?", kb(btns))
        return

    if text == "⚔️ Объявить войну" and is_commander(p):
        btns = [[fname] for fname in FACTIONS if fname != p["faction"]]
        btns.append([("◀️ Назад", "secondary")])
        p["temp"] = "diplo_war"
        save_player(p)
        send(vk, p["vk_id"], "⚔️ На кого объявить войну?", kb(btns))
        return

    if temp == "diplo_ally" and text in FACTIONS:
        rel = get_faction_relations()
        current = rel.get(p["faction"], {}).get(text, 0)
        if current < 20:
            send(vk, p["vk_id"],
                 f"Невозможно. Для союза нужны хорошие отношения (текущие: {current}).", None)
            screen_diplomacy(vk, p)
            return
        adjust_faction_relations(p["faction"], text, 30)
        p["temp"] = ""
        save_player(p)
        send(vk, p["vk_id"], f"🤝 Союз с {text} заключён.", None)
        screen_main(vk, p)
        return

    if temp == "diplo_war" and text in FACTIONS:
        adjust_faction_relations(p["faction"], text, -50)
        p["temp"] = ""
        save_player(p)
        send(vk, p["vk_id"], f"⚔️ Война с {text} объявлена.", None)
        screen_main(vk, p)
        return

    # ── Атака игрока ──
    if text.startswith("⚔️ Атаковать "):
        target_name = text[13:]
        players_here = get_players_in_sector(p["current_sec"], exclude_vk_id=p["vk_id"])
        target = next((pl for pl in players_here if pl["name"] == target_name), None)
        if not target:
            send(vk, p["vk_id"], "Игрок уже ушёл.", None)
            screen_main(vk, p)
            return
        t_full = get_player(target["vk_id"])
        if not t_full:
            screen_main(vk, p)
            return
        enemy_data = {
            "name": f"[{t_full['faction']}] {t_full['name']}",
            "hp": t_full["hp"], "max_hp": t_full["max_hp"],
            "dmg_range": [max(1, calc_stats(t_full)["attack"] - 5),
                          calc_stats(t_full)["attack"] + 5],
            "exp": 30, "tokens": [20, 50],
            "is_player": True, "player_id": t_full["vk_id"],
        }
        # Оповещаем атакованного
        try:
            notify(vk, t_full["vk_id"],
                   f"⚠️ Тебя атакует {p['name']} [{p['faction']}]!\nСектор: {ALL_SECTORS.get(p['current_sec'],{}).get('name','?')}")
        except Exception:
            pass
        start_battle(vk, p, enemy_data)
        return

    # Fallback
    screen_main(vk, p)

def _screen_equip_art(vk, p):
    inv_arts = {k: v for k, v in p["inventory"].items() if k in ARTIFACTS and v > 0}
    if not inv_arts:
        send(vk, p["vk_id"], "Нет артефактов на складе.", None)
        screen_equipment(vk, p)
        return
    slots_used = art_slots_used(p)
    slots_max = art_slots_max(p)
    if slots_used >= slots_max:
        send(vk, p["vk_id"],
             f"Все слоты заняты ({slots_used}/{slots_max}).\nКупи броню с большим числом слотов.", None)
        screen_equipment(vk, p)
        return
    btns = []
    for name in inv_arts:
        art = ARTIFACTS[name]
        btns.append([(f"Надеть: {name}"[:40], "positive")])
    btns.append([("◀️ Назад", "secondary")])
    p["temp"] = "equip_art"
    save_player(p)
    send(vk, p["vk_id"], f"💎 Свободных слотов: {slots_max-slots_used}/{slots_max}", kb(btns))

def _screen_unequip_art(vk, p):
    if not p["equipped_artifacts"]:
        send(vk, p["vk_id"], "Нет надетых артефактов.", None)
        screen_equipment(vk, p)
        return
    btns = [[f"Снять: {name}"] for name in p["equipped_artifacts"]]
    btns.append([("◀️ Назад", "secondary")])
    p["temp"] = "unequip_art"
    save_player(p)
    send(vk, p["vk_id"], "💎 Что снять?", kb(btns))

# ══════════════════════════════════════════════════════════
#  WEBHOOK
# ══════════════════════════════════════════════════════════

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
