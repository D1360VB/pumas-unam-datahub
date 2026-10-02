#!/usr/bin/env python3
"""
Scraper de datos de Pumas UNAM desde football-data.co.uk.

Descarga el CSV de la Liga MX, filtra los partidos donde participa
UNAM Pumas y guarda el resultado en data/raw/.

Formato del CSV (football-data.co.uk/new/MEX.csv):
    Country, League, Season, Date, Time, Home, Away, HG, AG, Res, ...
Encoding: UTF-8 con BOM (utf-8-sig)
"""

import os
import sys
import requests
import pandas as pd
from datetime import datetime

# --- Configuración ---
MEX_CSV_URL = "https://www.football-data.co.uk/new/MEX.csv"
CSV_ENCODING = "utf-8-sig"
PUMAS_NAME = "UNAM Pumas"

# --- Rutas ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")


def download_mex_csv():
    """Descarga el CSV de Liga MX y lo guarda con la fecha del día."""
    os.makedirs(RAW_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"MEX_{today}.csv"
    filepath = os.path.join(RAW_DIR, filename)

    print(f"⬇️  Descargando {MEX_CSV_URL}...")
    try:
        response = requests.get(MEX_CSV_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error al descargar: {e}")
        sys.exit(1)

    with open(filepath, "wb") as f:
        f.write(response.content)

    print(f"✅ Guardado en: {filepath}")
    return filepath


def filter_pumas_data(filepath):
    """
    Lee el CSV y filtra solo los partidos donde participa UNAM Pumas.

    Args:
        filepath: ruta al CSV crudo.

    Returns:
        DataFrame con los partidos de Pumas.
    """
    df = pd.read_csv(filepath, encoding=CSV_ENCODING)

    # Verificar columnas esperadas (falla temprano si el formato cambió)
    columnas_necesarias = ["Date", "Season", "Home", "Away", "HG", "AG", "Res"]
    faltantes = [c for c in columnas_necesarias if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Columnas faltantes: {faltantes}. "
            f"Disponibles: {df.columns.tolist()}"
        )

    # Filtrar partidos de Pumas (local o visitante)
    pumas_mask = (df["Home"] == PUMAS_NAME) | (df["Away"] == PUMAS_NAME)
    pumas_df = df[pumas_mask].copy()

    print(f"📊 Partidos de Pumas encontrados: {len(pumas_df)}")
    return pumas_df


def save_processed(pumas_df, source_filepath):
    """Guarda el DataFrame filtrado como CSV procesado."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # Nombre basado en el archivo fuente
    base = os.path.basename(source_filepath).replace(".csv", "")
    out_path = os.path.join(PROCESSED_DIR, f"pumas_{base}.csv")

    pumas_df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"💾 Procesado guardado en: {out_path}")
    return out_path


def main():
    csv_path = download_mex_csv()
    pumas_df = filter_pumas_data(csv_path)

    if pumas_df.empty:
        print("⚠️  No se encontraron partidos de Pumas en el CSV.")
        return

    # Guardar versión procesada
    save_processed(pumas_df, csv_path)

    # --- Resumen por consola ---
    print("\n--- Últimos 5 partidos de Pumas ---")
    cols = ["Date", "Season", "Home", "Away", "HG", "AG", "Res"]
    print(pumas_df[cols].tail(5).to_string(index=False))

    print("\n--- Partidos por temporada ---")
    print(pumas_df["Season"].value_counts().sort_index().to_string())

    # Estadísticas rápidas
    print("\n--- Resumen ---")
    print(f"Total de partidos: {len(pumas_df)}")
    print(f"Temporadas cubiertas: {pumas_df['Season'].nunique()}")
    print(f"Rango de fechas: {pumas_df['Date'].min()} → {pumas_df['Date'].max()}")


if __name__ == "__main__":
    main()
