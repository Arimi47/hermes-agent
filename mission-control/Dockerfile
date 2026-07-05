# Mission Control (Next.js 15) — Container-Build fuer Hetzner.
# Auf Railway wurde via Nixpacks gebaut; dieses Dockerfile ist das
# Aequivalent fuer docker compose. Kein output:standalone in
# next.config.js (wuerde Railways `next start` stoeren, solange das
# Projekt dort als Fallback liegt) - daher voller node_modules-Copy.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
# package.json start: `next start -p ${PORT:-3000}` - npm laeuft via sh,
# die Expansion funktioniert; ohne PORT-Env landet er auf 3000.
CMD ["npm", "run", "start"]
