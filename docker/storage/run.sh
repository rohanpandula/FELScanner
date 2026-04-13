#!/bin/sh
# Bring up Redis in the background, then exec the stock Postgres entrypoint
# in the foreground so Postgres owns signal handling (tini is PID 1).

set -eu

REDIS_CFG=/etc/redis/redis.conf
REDIS_DATA_DIR=/data/redis

# Inject the password at runtime if provided.
if [ -n "${REDIS_PASSWORD:-}" ]; then
  if ! grep -q "^requirepass " "$REDIS_CFG"; then
    printf '\nrequirepass %s\n' "$REDIS_PASSWORD" >>"$REDIS_CFG"
  fi
fi

# The mounted redis data volume may come from the legacy redis:7-alpine image
# where ownership was a different UID. Re-take it so Redis can write AOF.
mkdir -p "$REDIS_DATA_DIR"
chown -R redis:redis "$REDIS_DATA_DIR" /etc/redis

# Migrate legacy AOF layout (single appendonly.aof at volume root) into the
# new multi-file layout that Redis 7.4+ uses.
if [ -f "$REDIS_DATA_DIR/appendonly.aof" ] && [ ! -d "$REDIS_DATA_DIR/appendonlydir" ]; then
  echo "[storage] migrating legacy AOF file into appendonlydir/"
  mkdir -p "$REDIS_DATA_DIR/appendonlydir"
  mv "$REDIS_DATA_DIR/appendonly.aof" "$REDIS_DATA_DIR/appendonlydir/" 2>/dev/null || true
  chown -R redis:redis "$REDIS_DATA_DIR"
fi

# Start Redis under its own user. Redis logs to stdout by default (which
# becomes the container log via tini).
su-exec redis redis-server "$REDIS_CFG" &
REDIS_PID=$!

# Stop Postgres if Redis dies unexpectedly — failing loud beats silent
# half-collapse, which is harder to diagnose.
trap 'echo "[storage] Redis exited, stopping Postgres"; kill -TERM 1 2>/dev/null || true' EXIT
( while kill -0 $REDIS_PID 2>/dev/null; do sleep 5; done; echo "[storage] redis pid $REDIS_PID gone" ) &

# Hand control to the official Postgres entrypoint (creates data dir on
# first boot, runs /docker-entrypoint-initdb.d/*.sql) and exec into postgres.
exec docker-entrypoint.sh postgres
