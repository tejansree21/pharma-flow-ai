# ─────────────────────────────────────────────────────────────────────────────
# PharmaFlow AI Dashboard — Dockerfile
# Multi-stage: Node build → nginx serve
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build React app ──────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --silent

COPY . .

# Build with production API URL baked in via env
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Stage 2: Serve with nginx ─────────────────────────────────────────────────
FROM nginx:1.25-alpine AS runtime

LABEL maintainer="PharmaFlow AI" \
      version="4.0.0" \
      description="PharmaFlow AI — React dashboard"

# Custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/health.txt || exit 1

CMD ["nginx", "-g", "daemon off;"]
