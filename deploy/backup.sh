#!/bin/sh
# Kunlik zaxira nusxa: PostgreSQL (pg_dump, custom format) + shifrlangan media fayllar.
# KEEP_DAYS kundan eskilari o'chiriladi. Tiklash: deploy/README.md → "Zaxiradan tiklash".
# Diqqat: media DATA_ENCRYPTION_KEY bilan shifrlangan — kalitni zaxiradan alohida, xavfsiz joyda saqlang.
set -eu

KEEP_DAYS="${KEEP_DAYS:-14}"
HOUR="${BACKUP_HOUR_UTC:-22}" # 22:00 UTC = 03:00 Toshkent
mkdir -p /backups

backup() {
  stamp=$(date -u +%Y-%m-%d_%H%M)
  pg_dump -Fc -f "/backups/db_${stamp}.dump.tmp" && mv "/backups/db_${stamp}.dump.tmp" "/backups/db_${stamp}.dump"
  tar -czf "/backups/media_${stamp}.tar.gz.tmp" -C /media . && mv "/backups/media_${stamp}.tar.gz.tmp" "/backups/media_${stamp}.tar.gz"
  find /backups -type f \( -name 'db_*.dump' -o -name 'media_*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
  echo "$(date -u) zaxira tayyor: db_${stamp}.dump, media_${stamp}.tar.gz"
}

# Qo'lda: docker compose -f deploy/docker-compose.yml exec backup sh /backup.sh once
if [ "${1:-}" = "once" ]; then
  backup
  exit 0
fi

# Har kuni belgilangan soatda. Ishga tushganda darhol olinmaydi: API migratsiyalari hali
# qo'llanmagan bo'lishi mumkin (bo'sh baza zaxirasi foydasiz)
while true; do
  now=$(date -u +%s)
  next=$(date -u -d "$(date -u +%Y-%m-%d) ${HOUR}:00:00" +%s 2>/dev/null || echo $((now + 86400)))
  [ "$next" -le "$now" ] && next=$((next + 86400))
  sleep $((next - now))
  backup || echo "$(date -u) ZAXIRA XATOSI" >&2
done
