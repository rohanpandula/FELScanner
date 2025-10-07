#!/usr/bin/env bash
set -euo pipefail

if [[ "${PLEX_URL:-}" == "" ]]; then
  echo "PLEX_URL environment variable is required" >&2
  exit 2
fi

if [[ "${PLEX_TOKEN:-}" == "" ]]; then
  echo "PLEX_TOKEN environment variable is required" >&2
  exit 2
fi

HOST_HEADER=${PLEX_HOST_HEADER:-}
CURL_ARGS=("-sS" "-m" "10" "${PLEX_URL%/}/status/sessions")
CURL_ARGS+=("-H" "X-Plex-Token: ${PLEX_TOKEN}")

if [[ -n "$HOST_HEADER" ]]; then
  CURL_ARGS+=("-H" "Host: ${HOST_HEADER}")
fi

if [[ "${INSECURE_SSL:-false}" == "true" ]]; then
  CURL_ARGS+=("-k")
fi

response=$(curl "${CURL_ARGS[@]}" || true)

if [[ -z "$response" ]]; then
  echo "No response from Plex server" >&2
  exit 3
fi

if echo "$response" | grep -q "<MediaContainer"; then
  echo "Plex connection successful"
  exit 0
fi

echo "Unexpected response from Plex server:" >&2
echo "$response" >&2
exit 4
