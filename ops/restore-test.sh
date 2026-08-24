#!/usr/bin/env sh
set -eu

project_dir=${IDML_PROJECT_DIR:-/opt/idml-platform}
backup_dir=${1:?backup directory required}
compose_file="$project_dir/deploy/docker-compose.dev.yml"
restore_db="idml_restore_test"

case "$backup_dir" in
  /opt/idml-platform/backups/*) ;;
  *) echo "backup path is outside the approved directory" >&2; exit 1 ;;
esac

cd "$project_dir"
cd "$backup_dir"
sha256sum -c SHA256SUMS

cd "$project_dir"
docker compose --env-file .env -f "$compose_file" exec -T postgres \
  dropdb -U "$IDML_POSTGRES_USER" --if-exists "$restore_db"
docker compose --env-file .env -f "$compose_file" exec -T postgres \
  createdb -U "$IDML_POSTGRES_USER" "$restore_db"
docker compose --env-file .env -f "$compose_file" exec -T postgres \
  pg_restore -U "$IDML_POSTGRES_USER" -d "$restore_db" --no-owner --no-privileges \
  < "$backup_dir/database.dump"
table_count=$(docker compose --env-file .env -f "$compose_file" exec -T postgres \
  psql -U "$IDML_POSTGRES_USER" -d "$restore_db" -Atc \
  "select count(*) from information_schema.tables where table_schema='public';")
test "$table_count" -ge 10
docker compose --env-file .env -f "$compose_file" exec -T postgres \
  dropdb -U "$IDML_POSTGRES_USER" "$restore_db"
printf 'restore test passed with %s public tables\n' "$table_count"

