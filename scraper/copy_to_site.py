#!/usr/bin/env python3
"""Copia los JSONs exportados a site/public/data/ para Astro."""

import os
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "data", "exports")
DEST_DIR = os.path.join(BASE_DIR, "site", "public", "data")

def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    for fname in os.listdir(SRC_DIR):
        if fname.endswith(".json"):
            shutil.copy2(
                os.path.join(SRC_DIR, fname),
                os.path.join(DEST_DIR, fname),
            )
            print(f"  📄 Copiado: {fname}")

if __name__ == "__main__":
    main()
