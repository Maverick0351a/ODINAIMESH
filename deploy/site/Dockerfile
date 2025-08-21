# ODIN Site - VitePress Documentation + BYOM Playground

FROM node:18-alpine as builder

# Set working directory
WORKDIR /app

# Copy package files
COPY docs/package*.json ./

# Install dependencies
RUN npm ci

# Copy docs source
COPY docs/ .

# Build site
RUN npm run build

# Production stage - NGINX
FROM nginx:alpine

# Copy built site
COPY --from=builder /app/.vitepress/dist /usr/share/nginx/html

# Copy nginx configuration
COPY deploy/site/nginx.conf /etc/nginx/nginx.conf

# Create non-root user
RUN addgroup -g 1000 -S odin && \
    adduser -u 1000 -S odin -G odin && \
    chown -R odin:odin /usr/share/nginx/html /var/cache/nginx /var/run /var/log/nginx

# Switch to non-root user
USER odin

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/ || exit 1

# Expose port
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
