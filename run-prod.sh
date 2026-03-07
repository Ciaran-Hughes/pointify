#!/bin/bash
# Build and start Pointify in production (Docker).
# Usage: ./run-prod.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -f ".env" ]; then
  echo "ERROR: .env not found. Copy backend/.env.example to .env and fill in values."
  exit 1
fi

echo "Building and starting Pointify (production)..."
docker-compose build
docker-compose up -d

echo ""
echo "Pointify is running."
echo "Configure Nginx Proxy Manager to route your domain to: pointify-frontend:80"
echo ""
echo "To view logs:   docker-compose logs -f"
echo "To stop:        docker-compose down"
