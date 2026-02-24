FROM node:20-alpine AS deps
WORKDIR /workspace
COPY apps/web/package.json /workspace/package.json
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /workspace
ENV NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /workspace/node_modules /workspace/node_modules
COPY apps/web /workspace
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /workspace
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /workspace/public /workspace/public
COPY --from=builder /workspace/.next/standalone /workspace
COPY --from=builder /workspace/.next/static /workspace/.next/static
EXPOSE 3000
CMD ["node", "server.js"]
