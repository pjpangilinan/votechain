#!/usr/bin/env bash
# Exit on error
set -o errexit

# Explicitly set the settings module for the build process
export DJANGO_SETTINGS_MODULE=backend.settings

# 1. Install all the Python libraries from requirements.txt
pip install -r requirements.txt

# 2. Collect static files (CSS, JS, Images)
# This gathers admin files so WhiteNoise can serve them
python manage.py collectstatic --no-input

python manage.py createsuperuser --no-input --username=$DJANGO_SUPERUSER_USERNAME --email=$DJANGO_SUPERUSER_EMAIL

# 3. Run the database migrations
python manage.py migrate
