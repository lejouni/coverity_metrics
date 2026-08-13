#!/usr/bin/env bash
# coverity-export.sh — quickstart for coverity-export on Linux.
#
# Downloads the coverity-metrics standalone binary for the given release tag
# (or the latest release), sets the required connection environment variables,
# and runs `coverity-metrics export`. No Python install required on the host.
#
# EDIT the "EDIT THESE VALUES" block below to match your environment, or export
# the same variable names from your shell before running this script — the ':='
# fallbacks will not overwrite already-set values.

set -euo pipefail

# --------------------------------------------------------------------------- #
# EDIT THESE VALUES to point at your Coverity Postgres database.
# --------------------------------------------------------------------------- #
: "${COVERITY_DB_HOST:=coverity-prod.company.com}"
: "${COVERITY_DB_PORT:=5432}"
: "${COVERITY_DB_NAME:=cim}"
: "${COVERITY_DB_USER:=coverity_ro}"
: "${COVERITY_DB_PASSWORD:=change-me}"
: "${COVERITY_INSTANCE_NAME:=Production}"
# --------------------------------------------------------------------------- #

export COVERITY_DB_HOST COVERITY_DB_PORT COVERITY_DB_NAME
export COVERITY_DB_USER COVERITY_DB_PASSWORD COVERITY_INSTANCE_NAME

REPO="lejouni/coverity_metrics"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${BIN_DIR:-${SCRIPT_DIR}/bin}"

TAG=""
CONFIG=""
OUTPUT="exports"
DAYS=365
PROJECT=""
WORKERS=1
ANONYMIZE=0
NO_SNAPSHOTS=0
NO_LEADERBOARDS=0
VERBOSE=0
CACERT="${CURL_CA_BUNDLE:-${SSL_CERT_FILE:-}}"
INSECURE=0

usage() {
  cat <<EOF
Usage: $0 [--tag vX.Y.Z] [--config FILE] [--output DIR] [--days N]
          [--project NAMES] [--workers N] [--anonymize]
          [--no-snapshots] [--no-leaderboards]
          [--cacert PATH] [--insecure] [-v|--verbose] [-h|--help]

Downloads the coverity-metrics binary for the given release tag (or the
latest release when --tag is omitted) and runs 'coverity-metrics export'.
By default the connection details come from the environment variables
configured at the top of this script. Pass --config FILE to use a JSON
configuration file instead (multi-instance supported); the env-var block
and the placeholder-password guard are then skipped.

Options:
  --tag vX.Y.Z          Release tag to download (default: latest)
  --config FILE         Use a config.json instead of environment variables.
                        Multi-instance configuration is supported here.
  --output DIR          Output directory (default: exports)
  --days N              Trend analysis window in days (default: 365)
  --project NAMES       Comma-separated project filter (default: all)
  --workers N           Number of parallel workers for per-project export
                        (default: 1, capped at 8 by the binary). Each worker
                        opens its own Postgres connection.
  --anonymize           Replace real project/stream names with sequential ids
                        and write a sibling <zip>.mapping.json file
  --no-snapshots        Skip the Snapshots metric (privacy)
  --no-leaderboards     Skip the Leaderboards metrics (privacy)
  --cacert PATH         Path to a CA bundle for curl to trust (e.g. your
                        corporate root CA). Also picks up CURL_CA_BUNDLE or
                        SSL_CERT_FILE from the environment.
  --insecure            Skip TLS certificate verification when downloading the
                        binary (curl -k). Use only if you've already validated
                        the download by other means — last-resort escape hatch
                        for environments with broken TLS chains.
  -v, --verbose         Show per-metric '[SKIP] project/metric: No data' lines
                        (off by default; a summary count is always printed).
  -h, --help            Show this help

Environment overrides (set before running):
  COVERITY_DB_HOST, COVERITY_DB_PORT, COVERITY_DB_NAME,
  COVERITY_DB_USER, COVERITY_DB_PASSWORD, COVERITY_INSTANCE_NAME
  BIN_DIR (where to cache the downloaded binary; default: ./bin next to script)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)              TAG="${2:?--tag requires a value}"; shift 2 ;;
    --config)           CONFIG="${2:?--config requires a value}"; shift 2 ;;
    --output)           OUTPUT="${2:?--output requires a value}"; shift 2 ;;
    --days)             DAYS="${2:?--days requires a value}"; shift 2 ;;
    --project)          PROJECT="${2:?--project requires a value}"; shift 2 ;;
    --workers)          WORKERS="${2:?--workers requires a value}"; shift 2 ;;
    --anonymize)        ANONYMIZE=1; shift ;;
    --no-snapshots)     NO_SNAPSHOTS=1; shift ;;
    --no-leaderboards)  NO_LEADERBOARDS=1; shift ;;
    --cacert)           CACERT="${2:?--cacert requires a value}"; shift 2 ;;
    --insecure)         INSECURE=1; shift ;;
    -v|--verbose)       VERBOSE=1; shift ;;
    -h|--help)          usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

command -v curl >/dev/null || { echo "ERROR: 'curl' is required." >&2; exit 1; }

# Build the shared TLS options for every curl call in this script.
CURL_TLS_OPTS=()
if (( INSECURE == 1 )); then
  echo "WARNING: --insecure set — skipping TLS certificate verification on GitHub downloads." >&2
  CURL_TLS_OPTS+=(-k)
elif [[ -n "$CACERT" ]]; then
  if [[ ! -r "$CACERT" ]]; then
    echo "ERROR: CA bundle not readable: $CACERT" >&2
    exit 1
  fi
  echo "Using CA bundle: $CACERT"
  CURL_TLS_OPTS+=(--cacert "$CACERT")
fi

BIN_PATH=""

# When --tag is not supplied, prefer a cached binary from a previous run so
# we don't hit the GitHub API (or the network at all) unnecessarily.
if [[ -z "$TAG" && -d "$BIN_DIR" ]]; then
  cached=$(ls -1t "$BIN_DIR"/coverity-metrics-linux-* 2>/dev/null | head -n1 || true)
  if [[ -n "$cached" && -x "$cached" ]]; then
    BIN_PATH="$cached"
    TAG="${cached##*/coverity-metrics-linux-}"
    echo "Using cached binary: ${BIN_PATH} (tag ${TAG})"
  fi
fi

# Resolve latest tag from the GitHub API only if we still don't know one.
if [[ -z "$TAG" ]]; then
  echo "Resolving latest release tag from GitHub..."
  api_url="https://api.github.com/repos/${REPO}/releases/latest"
  TAG=$(curl "${CURL_TLS_OPTS[@]}" -fsSL "$api_url" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)
  if [[ -z "$TAG" ]]; then
    echo "ERROR: Could not resolve latest tag from ${api_url}" >&2
    exit 1
  fi
  echo "Latest tag: ${TAG}"
fi

BIN_NAME="coverity-metrics-linux-${TAG}"
if [[ -z "$BIN_PATH" ]]; then
  BIN_PATH="${BIN_DIR}/${BIN_NAME}"
fi
URL="https://github.com/${REPO}/releases/download/${TAG}/${BIN_NAME}"

if [[ -x "$BIN_PATH" ]]; then
  echo "Using cached binary: ${BIN_PATH}"
else
  echo "Downloading ${URL}"
  mkdir -p "$BIN_DIR"
  if ! curl "${CURL_TLS_OPTS[@]}" -fL --retry 3 --output "$BIN_PATH" "$URL"; then
    rm -f "$BIN_PATH"
    echo "ERROR: Failed to download ${URL}" >&2
    exit 1
  fi
  chmod +x "$BIN_PATH"
fi

# Refuse to run with the placeholder password so nobody triggers a real export
# with an unedited copy of this script. When --config is used, connection
# details come from the file so the env-var guard is irrelevant.
if [[ -z "$CONFIG" && "$COVERITY_DB_PASSWORD" == "change-me" ]]; then
  echo "ERROR: COVERITY_DB_PASSWORD is still the placeholder value 'change-me'." >&2
  echo "Edit this script (or export COVERITY_DB_PASSWORD, or pass --config FILE) before running." >&2
  exit 1
fi

cmd=("$BIN_PATH" export --output "$OUTPUT" --days "$DAYS" --workers "$WORKERS")
[[ -n "$CONFIG" ]] && cmd+=(--config "$CONFIG")
[[ -n "$PROJECT" ]] && cmd+=(--project "$PROJECT")
(( ANONYMIZE == 1 )) && cmd+=(--anonymize)
(( NO_SNAPSHOTS == 1 )) && cmd+=(--no-snapshots)
(( NO_LEADERBOARDS == 1 )) && cmd+=(--no-leaderboards)
(( VERBOSE == 1 )) && cmd+=(--verbose)

cat <<INFO

Config   : ${CONFIG:-<env vars>}
Instance : ${COVERITY_INSTANCE_NAME}
Host     : ${COVERITY_DB_HOST}
Database : ${COVERITY_DB_NAME}
User     : ${COVERITY_DB_USER}
Output   : ${OUTPUT}
Days     : ${DAYS}
Workers  : ${WORKERS}
Binary   : ${BIN_PATH}

Running: ${cmd[*]}

INFO

"${cmd[@]}"
