#!/bin/bash
# stop.sh - Script để stop toàn bộ services

echo "Stopping Docker services..."
docker-compose down
echo "Services stopped!"
