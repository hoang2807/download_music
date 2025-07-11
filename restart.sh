#!/bin/bash
# restart.sh - Script để restart services

echo "Restarting Docker services..."
docker-compose down
docker-compose up -d --build
echo "Services restarted!"