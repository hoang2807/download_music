#!/bin/bash

# SSL Renewal Script
echo "Checking for SSL certificate renewal..."

# Renew certificates
docker-compose run --rm certbot renew

# Reload nginx if renewal was successful
if [ $? -eq 0 ]; then
    echo "Certificate renewed successfully!"
    docker-compose exec nginx nginx -s reload
    echo "Nginx reloaded with new certificate"
else
    echo "No renewal needed or renewal failed"
fi