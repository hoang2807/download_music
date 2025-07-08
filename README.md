# Build docker

Install package (git, docker, docker compose)

```bash
sudo apt update
sudo apt install git (https://git-scm.com/downloads/linux)
sudo apt install docker.io docker-compose
https://docs.docker.com/engine/install/ubuntu/
https://docs.docker.com/compose/install/linux/
```

Run command in terminal

```bash
docker compose build (build image)
docker compose up -d (chạy các container ở background)
```

phpMyAdmin: localhost:8080
username: ytuser
password: ytpassword

run ssl

```bash
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email hungnm.dev94@gmail.com \
  --agree-tos \
  --no-eff-email \
  -d scraper.merrychill.com
```

Note: Open port 80, 443