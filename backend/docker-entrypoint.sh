#!/bin/sh
set -eu

app_user="${FLATWORLD_APP_USER:-app}"
app_uid="${FLATWORLD_APP_UID:-1000}"
app_gid="${FLATWORLD_APP_GID:-1000}"
data_dir="${FLATWORLD_DATA_DIR:-/data}"

if [ "$(id -u)" -ne 0 ]; then
  echo "[entrypoint] non-root startup; continuing as UID $(id -u)"
  exec "$@"
fi

mkdir -p "$data_dir"
if [ "$(stat -c '%u:%g' "$data_dir")" != "${app_uid}:${app_gid}" ]; then
  chown -R "${app_uid}:${app_gid}" "$data_dir"
fi

if command -v setpriv >/dev/null 2>&1; then
  exec setpriv --reuid="${app_uid}" --regid="${app_gid}" --init-groups "$@"
fi

exec su -s /bin/sh -c 'exec "$@"' -- "${app_user}" sh "$@"
