#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install all the Python libraries from requirements.txt
pip install -r requirements.txt

# 2. Run the database migrations (create tables in the new DB)
python manage.py migrate
