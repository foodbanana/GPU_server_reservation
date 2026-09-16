#!/usr/bin/env bash
#
# GPU 예약 시스템 DB 백업 (Phase 5)
#
# 서버가 **켜져 있는 채로 실행해도 안전하다.**
# 그냥 `cp` 로 복사하면 마침 저장 중인 순간에 반쪽짜리 파일이 나올 수 있다.
# 그래서 SQLite 가 공식으로 제공하는 "온라인 백업(Online Backup API)"을 쓴다.
# 이 방식은 DB 를 잠깐씩 잠그면서 한 조각씩 안전하게 복사하므로,
# 예약이 동시에 들어와도 깨지지 않은 백업 파일이 나온다.
#
# 쓰는 법:
#   /home/taeung/GPU_server_reservation_ws/deploy/backup_db.sh
#
# 설정 바꾸기 (백업 폴더를 외장 디스크나 다른 서버로 옮길 때):
#   1) deploy/backup.conf.example 을 deploy/backup.conf 로 복사하고 값을 고친다. 또는
#   2) 환경변수로 준다:  BACKUP_DIR=/mnt/외장디스크/gpu-backup ./backup_db.sh
#
# 결과: 기본값 기준 ~/gpu-reserve-backups/gpu_2026-09-16.db 처럼 날짜별 파일이 쌓이고,
#       $KEEP_DAYS(기본 30)일 지난 백업은 자동으로 지워진다.

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$DEPLOY_DIR")"

# ---------- 1) 값을 정하는 순서: 환경변수 > deploy/backup.conf > 기본값 ----------
# 명령 앞에 직접 준 환경변수를 먼저 기억해 둔다.
#   예) BACKUP_DIR=/mnt/외장디스크/gpu-backup ./backup_db.sh
_ENV_DB_PATH="${DB_PATH:-}"
_ENV_BACKUP_DIR="${BACKUP_DIR:-}"
_ENV_KEEP_DAYS="${KEEP_DAYS:-}"

# 설정 파일이 있으면 읽는다 (백업 폴더를 외장 디스크로 옮길 때 여기만 고치면 된다)
CONF_FILE="${BACKUP_CONF:-$DEPLOY_DIR/backup.conf}"
if [ -f "$CONF_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONF_FILE"
fi

# 환경변수로 준 값이 설정 파일보다 우선
[ -n "$_ENV_DB_PATH" ] && DB_PATH="$_ENV_DB_PATH"
[ -n "$_ENV_BACKUP_DIR" ] && BACKUP_DIR="$_ENV_BACKUP_DIR"
[ -n "$_ENV_KEEP_DAYS" ] && KEEP_DAYS="$_ENV_KEEP_DAYS"

# 아무 데서도 정하지 않았으면 기본값
DB_PATH="${DB_PATH:-$REPO_DIR/data/gpu.db}"          # 백업할 운영 DB
BACKUP_DIR="${BACKUP_DIR:-$HOME/gpu-reserve-backups}" # 백업을 쌓아 둘 폴더
KEEP_DAYS="${KEEP_DAYS:-30}"                         # 며칠 지난 백업을 지울지

# ---------- 2) 백업에 쓸 파이썬 고르기 ----------
# venv 파이썬이 있으면 그걸 쓰고, 없으면 시스템 python3 을 쓴다.
# sqlite3 모듈은 파이썬에 기본으로 들어 있어서 따로 설치할 것이 없다.
PYTHON="$REPO_DIR/backend/venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "오류: python3 을 찾지 못했습니다." >&2
  exit 1
fi
# ROS 경로가 섞여 들어오는 것을 막는다 (이 컴퓨터 전용 주의사항)
export PYTHONPATH=

# ---------- 3) 확인 ----------
if [ ! -f "$DB_PATH" ]; then
  echo "오류: DB 파일이 없습니다: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y-%m-%d)"
TARGET="$BACKUP_DIR/gpu_$STAMP.db"
TMP="$TARGET.tmp"
LOG="$BACKUP_DIR/backup.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ---------- 4) 온라인 백업 ----------
rm -f "$TMP"
"$PYTHON" - "$DB_PATH" "$TMP" <<'PY'
import sqlite3
import sys

src_path, dst_path = sys.argv[1], sys.argv[2]

src = sqlite3.connect(src_path, timeout=30)
dst = sqlite3.connect(dst_path)
try:
    # 서버가 돌고 있어도 안전한 방식. 중간에 DB가 바뀌면 sqlite 가 알아서 다시 읽는다.
    src.backup(dst)
    # 복사한 파일이 깨지지 않았는지 확인한다.
    result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"백업 파일 검사 실패: {result}")
finally:
    dst.close()
    src.close()
PY

# 검사까지 통과한 뒤에야 진짜 이름으로 바꾼다.
# (중간에 실패하면 .tmp 만 남고, 어제 백업은 그대로 보존된다)
mv -f "$TMP" "$TARGET"
SIZE="$(du -h "$TARGET" | cut -f1)"
log "백업 완료: $TARGET ($SIZE)"

# ---------- 5) 오래된 백업 정리 ----------
DELETED="$(find "$BACKUP_DIR" -maxdepth 1 -name 'gpu_*.db' -type f -mtime "+$KEEP_DAYS" -print -delete | wc -l)"
if [ "$DELETED" -gt 0 ]; then
  log "$KEEP_DAYS일 지난 백업 $DELETED개 삭제"
fi
