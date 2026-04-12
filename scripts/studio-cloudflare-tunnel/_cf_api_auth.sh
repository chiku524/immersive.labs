#!/usr/bin/env bash
# shellcheck shell=bash
# Shared curl auth for Cloudflare v4 API. Source from other scripts after loading .env:
#   source "$SCRIPT_DIR/_cf_api_auth.sh"
#
# Authentication (first match wins):
#   1) CF_GLOBAL_API_KEY + CF_AUTH_EMAIL  → X-Auth-Key + X-Auth-Email (Global API Key)
#   2) CLOUDFLARE_API_TOKEN               → Authorization: Bearer (User or Account API token)
#
_cf_api_curl() {
  if [[ -n "${CF_GLOBAL_API_KEY:-}" && -n "${CF_AUTH_EMAIL:-}" ]]; then
    curl -fsS --max-time 60 \
      -H "X-Auth-Email: ${CF_AUTH_EMAIL}" \
      -H "X-Auth-Key: ${CF_GLOBAL_API_KEY}" \
      "$@"
  elif [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    curl -fsS --max-time 60 \
      -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
      "$@"
  else
    echo "_cf_api_curl: set CLOUDFLARE_API_TOKEN or CF_GLOBAL_API_KEY+CF_AUTH_EMAIL in .env" >&2
    return 1
  fi
}
