#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Převede statické soubory (CSS) pro server
python manage.py collectstatic --no-input

# Vytvoří tabulky v databázi
python manage.py migrate