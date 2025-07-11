#!/bin/bash
# status.sh - Script để check status

echo "Docker services status:"
docker-compose ps

echo ""
echo "Redis connection test:"
docker-compose exec redis redis-cli ping

echo ""
echo "Worker count:"
docker-compose ps worker | wc -l

echo ""
echo "System resources:"
docker stats --no-stream