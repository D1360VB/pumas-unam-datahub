#!/usr/bin/env python3
"""
Exporta datos de SQLite a JSON para el sitio web estático.
"""

import os
import json
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "ligamx.db")
EXPORT_DIR = os.path.join(BASE_DIR, "data", "exports")


def query_to_list(conn, sql, params=None):
    """Ejecuta SQL y devuelve lista de diccionarios."""
    cursor = conn.cursor()
    cursor.execute(sql, params or [])
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def export_all():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # 1. Todos los partidos (para la tabla principal)
    partidos = query_to_list(conn, """
        SELECT match_id, date, season, home_team, away_team,
               home_goals, away_goals, result, points, goal_diff
        FROM matches
        ORDER BY date DESC
    """)
    write_json(os.path.join(EXPORT_DIR, "matches.json"), partidos)

    # 2. Resumen por temporada
    temporadas = query_to_list(conn, """
        SELECT season,
               COUNT(*) as partidos,
               SUM(points) as puntos,
               SUM(pumas_goals) as goles_favor,
               SUM(rival_goals) as goles_contra,
               SUM(CASE WHEN result='W' THEN 1 ELSE 0 END) as ganados,
               SUM(CASE WHEN result='D' THEN 1 ELSE 0 END) as empatados,
               SUM(CASE WHEN result='L' THEN 1 ELSE 0 END) as perdidos
        FROM matches
        GROUP BY season
        ORDER BY season DESC
    """)
    write_json(os.path.join(EXPORT_DIR, "seasons.json"), temporadas)

    # 3. Estadísticas vs rivales
    rivales = query_to_list(conn, """
        SELECT rival,
               COUNT(*) as partidos,
               SUM(points) as puntos,
               SUM(CASE WHEN result='W' THEN 1 ELSE 0 END) as ganados,
               SUM(CASE WHEN result='D' THEN 1 ELSE 0 END) as empatados,
               SUM(CASE WHEN result='L' THEN 1 ELSE 0 END) as perdidos
        FROM matches
        GROUP BY rival
        ORDER BY puntos DESC
    """)
    write_json(os.path.join(EXPORT_DIR, "rivals.json"), rivales)

    # 4. Metadata
    metadata = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total_matches": len(partidos),
        "seasons_covered": len(temporadas),
    }
    write_json(os.path.join(EXPORT_DIR, "metadata.json"), metadata)

    conn.close()
    print(f"✅ Exportados 4 archivos JSON en {EXPORT_DIR}")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📄 {os.path.basename(path)}: {len(data)} registros")


if __name__ == "__main__":
    export_all()
