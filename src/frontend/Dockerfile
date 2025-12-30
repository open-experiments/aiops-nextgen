# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Production stage - use unprivileged nginx for OpenShift compatibility
FROM nginxinc/nginx-unprivileged:alpine

# Switch to root to copy config, then switch back
USER root

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set proper permissions
RUN chown -R nginx:nginx /etc/nginx/conf.d && \
    chmod -R 755 /etc/nginx/conf.d

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Set proper permissions for static files
RUN chown -R nginx:nginx /usr/share/nginx/html

# Switch back to nginx user
USER nginx

# Expose port 8080 (unprivileged nginx uses 8080 by default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
