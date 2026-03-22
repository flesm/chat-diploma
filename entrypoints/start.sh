#!/bin/bash
set -e

echo "Waiting for MongoDB..."
until nc -z chat_mongo 27017; do
  sleep 1
done

echo "Starting Chat FastAPI server..."
exec uvicorn src.app.main:app --host 0.0.0.0 --port 8010
