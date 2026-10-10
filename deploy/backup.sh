#!/bin/sh
# Run from repository root on the deployment host. Pause writes for a consistent pair.
set -eu
umask 077
backup_dir="${1:?Usage: sh deploy/backup.sh /absolute/backup-directory}"
mkdir -p "$backup_dir"
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose stop app maintenance
trap 'docker compose start app maintenance >/dev/null' EXIT INT TERM
docker compose exec -T db pg_dump -U bmsit -d bmsit -Fc > "$backup_dir/$backup_stamp.database.dump"
docker compose run --rm --no-deps -T maintenance tar -C /app/.data -czf - covers > "$backup_dir/$backup_stamp.media.tar.gz"
# S3 mode additionally requires a provider-side backup/versioning policy.
printf 'Created database and local-media backup: %s\n' "$backup_stamp"
