# Anveshak Frontend
# React + TypeScript SPA, served by nginx on port 3000
# Build context: frontend/
#
# Multi-stage build:
#   Stage 1 (builder) — npm install + vite build
#   Stage 2 (runtime) — nginx:alpine serving /usr/share/nginx/html

# --------------------------------------------------------------------------
# Stage 1: Build
# --------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (cached unless package.json / lock changes)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit

# Pass API base URL at build time (Vite bakes it into the JS bundle)
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Copy source and build
COPY frontend/ .
RUN npm run build

# --------------------------------------------------------------------------
# Stage 2: Runtime (nginx)
# --------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx config:
#   - Listens on port 3000 (not 80 — avoids running as root)
#   - try_files for SPA client-side routing
#   - Proxies /api/* to the api service (set at runtime via env sub)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# nginx needs write access to its temp dirs when running as non-root
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
