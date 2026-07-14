FROM node:22-alpine AS deps

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json ./frontend/package.json
RUN pnpm --filter frontend install --frozen-lockfile

FROM node:22-alpine AS builder

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/frontend/node_modules ./frontend/node_modules
COPY . .
WORKDIR /app/frontend
RUN pnpm build \
    && test -f .next/standalone/frontend/server.js

FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./

COPY --from=builder --chown=nextjs:nodejs \
    /app/frontend/.next/static ./frontend/.next/static

COPY --from=builder --chown=nextjs:nodejs \
    /app/frontend/public ./frontend/public

RUN test -f /app/frontend/server.js

USER nextjs

EXPOSE 3000

CMD ["node", "frontend/server.js"]
