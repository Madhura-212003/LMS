#!/usr/bin/env bash
set -euo pipefail
umask 077
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
env_file="$deploy_dir/.env.production"
compose=(docker compose --env-file "$env_file" -f "$deploy_dir/compose.production.yml")
if [[ ! -f "$env_file" ]]; then echo 'Create deploy/.env.production from the example and supply the institution values.' >&2; exit 1; fi
"${compose[@]}" config --quiet
# Extract only the image identifiers. Never print the resolved secret environment.
for service in backend frontend; do
  image="$("${compose[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"][sys.argv[1]]["image"])' "$service")"
  if [[ ! "$image" =~ @sha256:[a-f0-9]{64}$ ]]; then echo "$service must use an immutable image digest" >&2; exit 1; fi
done
"${compose[@]}" pull backend frontend
"${compose[@]}" run --rm --no-deps backend python manage.py deployment_check
mkdir -p "$deploy_dir/backups"
echo 'Stopping application writers for the backup and additive schema migration window.'
"${compose[@]}" stop worker backend frontend
echo 'Creating a pre-migration PostgreSQL backup. Keep this directory private and copy backups to the institution vault.'
"${compose[@]}" run --rm --no-deps db-tools sh -c 'umask 077; export PGHOST="$POSTGRES_HOST" PGPORT="${POSTGRES_PORT:-5432}" PGDATABASE="$POSTGRES_DB" PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" PGSSLMODE="${POSTGRES_SSLMODE:-require}"; pg_dump --format=custom --file="/backups/before-release-$(date -u +%Y%m%dT%H%M%SZ).dump"'
# Additive migrations precede the application rollout. No seed/reset/delete command is run.
"${compose[@]}" run --rm --no-deps backend python manage.py migrate --noinput
"${compose[@]}" run --rm --no-deps backend python manage.py rebuild_question_evidence
"${compose[@]}" up -d --wait backend worker frontend edge
"${compose[@]}" exec -T backend python manage.py deployment_check --live-services
echo 'Deployment checks passed. Complete the browser, SSO, video, private-file, language and accessibility checks in IT-HANDOFF.md before admitting learners.'
