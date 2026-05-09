#!/bin/bash
set -e

echo "🔄 Running database migrations..."
python -m alembic upgrade head 2>/dev/null || echo "⚠️  Migrations skipped (run manually if needed)"

echo "🚀 Starting Liriel Agent..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000} --workers 1
