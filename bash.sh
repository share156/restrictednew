#!/bin/bash
# Render / generic shell entrypoint.
#
# Render requires the `web` service to bind to $PORT within ~60s.
# We start gunicorn (Flask health-check) in the background to satisfy that,
# then run the Telegram bot in the foreground so the container stays alive.
set -e

echo "Starting Flask health-check server on $PORT..."
gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 1 &

echo "Starting SaveRestrictedContentBot..."
python3 -m main
