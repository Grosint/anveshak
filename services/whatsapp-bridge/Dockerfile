FROM node:20-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY services/whatsapp-bridge/package.json services/whatsapp-bridge/package-lock.json* ./
RUN npm ci --no-audit --production

COPY services/whatsapp-bridge/src/ src/

EXPOSE 3002

# Media files readable by other containers (social worker runs as anveshak user)
# Auth files protected by separate volume


CMD ["node", "src/index.js"]
