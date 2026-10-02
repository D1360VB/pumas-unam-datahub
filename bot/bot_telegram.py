#!/usr/bin/env python3
"""
Bot de Telegram para Pumas UNAM.
Publica un dato diario basado en los datos exportados de SQLite.

Uso:
    TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python bot/bot_telegram.py
"""

import os
import json
import random
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from telegram import Bot

# --- Rutas ---
BASE_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = BASE_DIR / "data" / "exports"
STATE_FILE = BASE_DIR / "data" / "bot_state.json"

# --- Credenciales (desde variables de entorno) ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def load_json(filename):
    """Carga un JSON de exports."""
    path = EXPORTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"No se encontró {path}. Ejecuta el pipeline ETL primero.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    """Carga el estado del bot (qué ya se publicó)."""
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"published_match_ids": [], "last_published": None}


def save_state(state):
    """Guarda el estado del bot."""
    os.makedirs(STATE_FILE.parent, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_daily_content(matches, seasons, state):
    """Selecciona el contenido del día."""
    published = set(state.get("published_match_ids", []))

    # Validación: si match_id es None en todos, es un error de datos
    if matches and all(m.get("match_id") is None for m in matches):
        raise ValueError(
            "❌ Todos los match_id son None. "
            "Revisa que scraper/etl.py esté generando los IDs correctamente."
        )

    for match in matches:
        mid = match.get("match_id")
        if mid and mid not in published:
            return {"type": "match", "data": match}

    if seasons:
        return {"type": "season", "data": seasons[0]}

    return None


def format_match_message(match):
    """Formatea un partido como mensaje para Telegram."""
    # El resultado ya viene como W/D/L desde la perspectiva de Pumas
    result_emoji = {"W": "🟢 Victoria", "D": "🟡 Empate", "L": "🔴 Derrota"}

    # Determinar si fue local o visitante por el formato del partido
    # El JSON tiene home_team y away_team, pero también rival e is_home
    # Usamos home_team para saber el contexto
    es_local = match.get("is_home", 0) == 1 if "is_home" in match else None

    # Construir el marcador desde la perspectiva del equipo
    # En matches.json tenemos home_goals y away_goals
    marcador = f"{match['home_goals']} - {match['away_goals']}"

    # Formatear fecha
    fecha = match.get("date", "")

    resultado = result_emoji.get(match.get("result", ""), "⚪")

    mensaje = (
        f"📅 **{fecha}** | {match.get('season', '')}\n\n"
        f"⚽ **{match['home_team']}** {marcador} **{match['away_team']}**\n\n"
        f"{resultado} | {match.get('points', 0)} pts\n"
        f"#PumasUNAM #LigaMX"
    )
    return mensaje


def format_season_message(season):
    """Formatea estadísticas de temporada como mensaje."""
    mensaje = (
        f"📊 **Resumen de temporada: {season['season']}**\n\n"
        f"Partidos jugados: {season['partidos']}\n"
        f"Puntos: {season['puntos']}\n"
        f"Goles a favor: {season['goles_favor']}\n"
        f"Goles en contra: {season['goles_contra']}\n\n"
        f"🟢 {season['ganados']} victorias | "
        f"🟡 {season['empatados']} empates | "
        f"🔴 {season['perdidos']} derrotas\n\n"
        f"#PumasUNAM #LigaMX"
    )
    return mensaje


async def publish():
    """Función principal: selecciona y publica el dato del día."""
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError(
            "Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID. "
            "Configúralos como variables de entorno o GitHub Secrets."
        )

    # Cargar datos
    matches = load_json("matches.json")
    seasons = load_json("seasons.json")
    metadata = load_json("metadata.json")

    print(f"📊 Datos cargados: {len(matches)} partidos, {len(seasons)} temporadas")
    print(f"🕐 Última actualización: {metadata.get('last_updated', 'desconocida')}")

    # Cargar estado
    state = load_state()

    # Seleccionar contenido
    content = pick_daily_content(matches, seasons, state)
    if not content:
        print("⚠️ No hay contenido nuevo para publicar.")
        return

    # Formatear mensaje
    if content["type"] == "match":
        message = format_match_message(content["data"])
        match_id = content["data"]["match_id"]
        print(f"📤 Publicando partido: {match_id}")
    else:
        message = format_season_message(content["data"])
        match_id = None
        print(f"📤 Publicando temporada: {content['data']['season']}")

    # Publicar en Telegram
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    print("✅ Mensaje publicado en Telegram")

    # Actualizar estado
    if match_id:
        state.setdefault("published_match_ids", []).append(match_id)
    state["last_published"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print(f"💾 Estado guardado: {len(state['published_match_ids'])} partidos publicados")


if __name__ == "__main__":
    asyncio.run(publish())
