# Web ilova (React) + Caddy: statik fayllar, /api → backend, avtomatik HTTPS (Let's Encrypt).
# Build konteksti — repo ildizi: docker compose -f deploy/docker-compose.yml build web
FROM node:22-alpine AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
# Telegram bot havolasi (masalan https://t.me/workly_bot) — build vaqtida kiritiladi
ARG VITE_BOT_URL=""
ENV VITE_BOT_URL=$VITE_BOT_URL
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
