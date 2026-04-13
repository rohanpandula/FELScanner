# syntax=docker/dockerfile:1.6
# Combined Postgres 15 + Redis 7 image.
# Postgres runs as the main foreground process (via its official entrypoint);
# Redis is started in the background by a small wrapper and reaped on exit.
# Supervisord-lite: plain shell, no extra deps, minimal failure modes.

FROM postgres:15-alpine

ARG REDIS_PACKAGE=redis

# Redis from Alpine repo, plus a process supervisor that we'll use to keep
# Redis alive if it crashes while Postgres keeps running.
RUN apk add --no-cache ${REDIS_PACKAGE} su-exec tini

# Redis data lives here, matching its default dir.
RUN mkdir -p /data/redis /etc/redis && chown -R redis:redis /data/redis /etc/redis

# Minimal Redis config. Auth + AOF persistence, same behaviour as the old
# standalone `redis:7-alpine` entrypoint.
RUN cat >/etc/redis/redis.conf <<'EOF'
bind 0.0.0.0
port 6379
dir /data/redis
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
maxmemory-policy noeviction
# requirepass is injected at runtime by the entrypoint when REDIS_PASSWORD is set.
EOF

COPY run.sh /usr/local/bin/run-storage
RUN chmod +x /usr/local/bin/run-storage

# Reuse the stock postgres healthcheck tooling; this container's overall health
# is "Postgres is ready AND Redis responds to PING".
HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
  CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" \
      && redis-cli -p 6379 ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} ping | grep -q PONG

ENTRYPOINT ["/sbin/tini", "-g", "--", "/usr/local/bin/run-storage"]
