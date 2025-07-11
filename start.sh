#!/bin/bash
# start.sh - Script để start toàn bộ services

echo "Starting Docker services..."

# Build và start services
docker-compose up -d --build

echo "Services started!"
echo "Web app: http://localhost:5000"
echo "Dashboard: http://localhost:5000/dashboard"

# Hiển thị logs
docker-compose logs -f