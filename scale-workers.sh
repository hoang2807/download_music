#!/bin/bash
# scale-workers.sh - Script để scale workers

if [ -z "$1" ]; then
    echo "Usage: $0 <number_of_workers>"
    echo "Example: $0 20"
    exit 1
fi

WORKER_COUNT=$1

echo "Scaling workers to $WORKER_COUNT..."
docker-compose up -d --scale worker=$WORKER_COUNT

echo "Workers scaled to $WORKER_COUNT!"
docker-compose ps worker