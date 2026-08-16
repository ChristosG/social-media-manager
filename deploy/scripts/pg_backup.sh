#!/bin/sh
# Nightly logical backup of the `npo` database (custom format → restorable with pg_restore).
# The FIRST line of defense against a bad migration / accidental DELETE. pgBackRest PITR is Phase 1.
# Env: PGHOST PGUSER PGPASSWORD PGDATABASE. Writes to /backups, prunes dumps older than 14 days.
set -eu

TS=$(date +%F-%H%M)
OUT="/backups/${PGDATABASE:-npo}-${TS}.dump"

echo "[pg_backup] $(date -u +%FT%TZ) dumping ${PGDATABASE:-npo} -> ${OUT}"
pg_dump -Fc -h "${PGHOST:-postgres}" -U "${PGUSER:-platform}" -d "${PGDATABASE:-npo}" -f "${OUT}"
echo "[pg_backup] done ($(du -h "${OUT}" | cut -f1)); pruning dumps older than 14 days"
find /backups -name "${PGDATABASE:-npo}-*.dump" -mtime +14 -delete
echo "[pg_backup] $(ls -1 /backups/${PGDATABASE:-npo}-*.dump 2>/dev/null | wc -l) dump(s) retained"
