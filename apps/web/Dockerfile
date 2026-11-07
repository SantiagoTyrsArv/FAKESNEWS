FROM node:22-slim AS base
WORKDIR /app
RUN corepack enable

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT=standalone
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Owned by the runtime user: the server writes its cache under .next/cache.
COPY --from=builder --chown=node:node /app/.next/standalone ./
# The standalone server leaves these two out, expecting a CDN.
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# The node image ships an unprivileged "node" user.
USER node

EXPOSE 3000
# server.js honors $PORT, which container platforms inject.
CMD ["node", "server.js"]
