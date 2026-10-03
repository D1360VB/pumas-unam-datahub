#!/usr/bin/env python3
"""
ETL: Transforma los CSVs procesados de Pumas en una base de datos SQLite.

Pipeline:
    data/processed/pumas_*.csv → data/ligamx.db

Diseño idempotente: usa UPSERT (INSERT OR REPLACE) para que
re-ejecutar no duplique partidos.
"""

import os
import glob
import sqlite3
import pandas as pd
from datetime import datetime

# --- Rutas ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DB_PATH = os.path.join(BASE_DIR, "data", "ligamx.db")
DATE_FORMAT = "%d/%m/%Y"


def get_latest_processed_csv():
    """Encuentra el CSV procesado más reciente (por nombre con fecha)."""
    pattern = os.path.join(PROCESSED_DIR, "pumas_*.csv")
    archivos = sorted(glob.glob(pattern), reverse=True)
    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron CSVs procesados en {PROCESSED_DIR}. "
            "Ejecuta primero: python scraper/fetch_data.py"
        )
    return archivos[0]


def load_and_transform(filepath):
    """Lee el CSV procesado y añade columnas derivadas."""
    df = pd.read_csv(filepath, encoding="utf-8")

    # Parseo flexible de fecha (acepta ISO y DD/MM/YYYY)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Verificar que no haya fechas inválidas
    nulos = df["Date"].isna().sum()
    if nulos > 0:
        print(f"⚠️  {nulos} fechas inválidas encontradas; se eliminarán.")
        df = df.dropna(subset=["Date"]).reset_index(drop=True)

    # Columnas derivadas desde la perspectiva de Pumas
    es_local = df["Home"] == "UNAM Pumas"

    goles_pumas = df["HG"].where(es_local, df["AG"])
    goles_rival = df["AG"].where(es_local, df["HG"])
    df["pumas_goals"] = goles_pumas
    df["rival_goals"] = goles_rival
    df["rival"] = df["Away"].where(es_local, df["Home"])
    df["is_home"] = es_local.astype(int)

    # Resultado (W/D/L)
    condiciones = [
        goles_pumas > goles_rival,
        goles_pumas == goles_rival,
        goles_pumas < goles_rival,
    ]
    df["result"] = "L"
    df.loc[condiciones[0], "result"] = "W"
    df.loc[condiciones[1], "result"] = "D"

    # Puntos (3/1/0)
    df["points"] = df["result"].map({"W": 3, "D": 1, "L": 0})

    # Diferencia de goles
    df["goal_diff"] = df["pumas_goals"] - df["rival_goals"]

    # ID único del partido
    df["match_id"] = (
        df["Date"].dt.strftime("%Y%m%d")
        + "_"
        + df["Home"].str.replace(" ", "_")
        + "_vs_"
        + df["Away"].str.replace(" ", "_")
    )

    return df


def save_to_sqlite(df, db_path):
    """Guarda el DataFrame en SQLite usando INSERT OR REPLACE (idempotente)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Crear tabla si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            date TEXT,
            season TEXT,
            league TEXT,
            home_team TEXT,
            away_team TEXT,
            home_goals INTEGER,
            away_goals INTEGER,
            result TEXT,
            pumas_goals INTEGER,
            rival_goals INTEGER,
            rival TEXT,
            is_home INTEGER,
            points INTEGER,
            goal_diff INTEGER
        )
    """)

    # UPSERT: INSERT OR REPLACE por match_id
    filas = df[[
    "match_id", "Date", "Season", "League",
    "Home", "Away", "HG", "AG", "result",    # ← usar "result" (minúscula), no "Res"
    "pumas_goals", "rival_goals", "rival",
    "is_home", "points", "goal_diff",
    ]].copy()

    filas.columns = [
        "match_id", "date", "season", "league",
        "home_team", "away_team", "home_goals", "away_goals", "result",
        "pumas_goals", "rival_goals", "rival",
        "is_home", "points", "goal_diff",
    ]

    # Convertir fecha a string ISO para SQLite
    filas["date"] = filas["date"].dt.strftime("%Y-%m-%d")
    
    # Verificar que no queden None
    assert filas["date"].notna().all(), "Hay fechas nulas después del parseo"
    assert filas["match_id"].notna().all(), "Hay match_id nulos"

    registros = filas.values.tolist()
    cursor.executemany("""
        INSERT OR REPLACE INTO matches VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, registros)

    conn.commit()

    # Estadísticas
    total = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    conn.close()

    print(f"✅ Base de datos actualizada: {total} partidos en {db_path}")
    return total


def main():
    csv_path = get_latest_processed_csv()
    print(f"📂 Procesando: {csv_path}")

    df = load_and_transform(csv_path)
    print(f"📊 {len(df)} partidos transformados")

    save_to_sqlite(df, DB_PATH)


if __name__ == "__main__":
    main()
