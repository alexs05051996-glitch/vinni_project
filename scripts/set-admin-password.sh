#!/usr/bin/env bash
#
# set-admin-password.sh - установка/смена пароля администратора vinni-landing.
#
# Пароль никогда не печатается: он генерируется (или читается из stdin) и
# передаётся в контейнер через stdin (не в аргументах командной строки).
#
# Использование:
#   ./set-admin-password.sh                 # сгенерировать новый надёжный пароль
#   printf '%s' 'MyStrongPass!' | ./set-admin-password.sh --stdin
#
# Переменные: ADMIN_EMAIL (по умолчанию admin@vinni.fyi),
#             CONTAINER (vinni-landing), CRED_FILE (/opt/vinni-landing/.admin-credentials)
set -euo pipefail

CONTAINER="${CONTAINER:-vinni-landing}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@vinni.fyi}"
CRED_FILE="${CRED_FILE:-/opt/vinni-landing/.admin-credentials}"

if [[ "${1:-}" == "--stdin" ]]; then
  NEW_PASSWORD="$(cat)"
else
  NEW_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
fi

if [[ ${#NEW_PASSWORD} -lt 12 ]]; then
  echo "Ошибка: пароль должен быть не короче 12 символов." >&2
  exit 1
fi

PYCODE='
import sys
import sqlite3
import bcrypt

email = sys.argv[1]
password = sys.stdin.readline().rstrip("\n")

pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
db = sqlite3.connect("/app/data/vinni.db")
cur = db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email))
db.commit()
if cur.rowcount != 1:
    raise SystemExit("admin user not found / not updated")

stored = db.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()[0]
print("updated rows:", cur.rowcount, "| verify:", bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")))
'

printf '%s\n' "$NEW_PASSWORD" | docker exec -i "$CONTAINER" python -c "$PYCODE" "$ADMIN_EMAIL"

umask 077
cat > "$CRED_FILE" <<EOF
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$NEW_PASSWORD
EOF
chmod 600 "$CRED_FILE"
chown root:root "$CRED_FILE" 2>/dev/null || true

echo "Готово. Пароль записан в $CRED_FILE (права 600)."
echo "Посмотреть: sudo cat $CRED_FILE"
