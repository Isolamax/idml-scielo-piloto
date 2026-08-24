#!/usr/bin/env sh
set -eu

project_dir=${IDML_PROJECT_DIR:-/opt/idml-platform}
backup_root=${IDML_BACKUP_ROOT:-/opt/idml-platform/backups}
compose_file="$project_dir/deploy/docker-compose.dev.yml"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="$backup_root/$timestamp"

umask 077
mkdir -p "$destination"
cd "$project_dir"

docker compose --env-file .env -f "$compose_file" exec -T postgres \
  pg_dump -U "$IDML_POSTGRES_USER" -d "$IDML_POSTGRES_DB" -Fc > "$destination/database.dump"

docker run --rm --read-only \
  -v idml_development_artifacts:/source:ro \
  -v "$destination:/backup" \
  alpine:3.21 sh -c 'cd /source && tar -czf /backup/artifacts.tar.gz .'

sha256sum "$destination/database.dump" "$destination/artifacts.tar.gz" > "$destination/SHA256SUMS"
chmod 600 "$destination"/*
printf '%s\n' "$destination"

