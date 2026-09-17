# MORIN GPU 예약 시스템

연구실 GPU 서버 3대(GPU 12장)의 사용 시간을 예약하고, 예약 현황을 시간표로 확인하는 웹 서비스.

- 같은 GPU에서 시간이 겹치는 예약은 서버가 거부한다.
- 예약 길이·기간 제한은 없다. (연구실 내 협의로 사용)
- 시간표는 2주 단위로 보여 주며, 이전/다음 2주로 이동할 수 있다.
- 모든 시간은 한국 시간(Asia/Seoul) 기준이다.

이 문서는 **서버 컴퓨터에 설치·운영·이전**하는 데 필요한 내용만 담는다.
요구사항은 `SPEC.md`, 설계는 `PLAN.md` 참고.

---

## 1. 검증 환경

현재 코드는 아래 환경에서 개발·검증되었다.

| 항목 | 버전 |
|---|---|
| OS | **Ubuntu 24.04 LTS** |
| Python | **3.12.3** (최소 3.10) |
| Node.js / npm | **24.21.0 / 11.19.0** (화면 빌드에만 필요) |
| 서비스 관리 | systemd |
| DB | SQLite (파일 1개, 별도 설치 불필요) |
| 백엔드 / 프론트엔드 | FastAPI / Vue 3 + Vite |

### 다른 OS·버전으로 옮길 때 확인할 것

- **Python은 3.10 이상이어야 한다.**
  `backend/requirements.txt` 에 고정된 fastapi 0.141.1 / uvicorn 0.53.0 / pytest 9.1.1 이 모두
  `Requires-Python >= 3.10` 이다. Ubuntu 20.04 의 기본 Python 은 3.8 이므로 별도 설치가 필요하다.
  (`deadsnakes` PPA 로 `python3.12` 와 `python3.12-venv` 를 설치하는 방법이 가장 간단하다)
  - 참고: `uvicorn[standard]` 가 끌어오는 `websockets` 최신판은 Python 3.11 이상을 요구한다.
    3.10 에서는 pip 이 자동으로 이전 버전을 고른다. 가능하면 **3.11 이상**을 쓴다.
- **pip 이 너무 오래되면 설치가 실패한다.** (bcrypt 5.0.0 등이 최신 wheel 형식을 쓴다)
  venv 를 만든 직후 `PYTHONPATH= venv/bin/pip install --upgrade pip` 를 먼저 실행한다.
- **`tzdata` 가 설치되어 있어야 한다.** 코드가 `zoneinfo.ZoneInfo("Asia/Seoul")` 로 시간을 계산한다.
  최소 설치 환경(컨테이너 등)에서는 `sudo apt install tzdata` 가 필요할 수 있다.
  시스템 시간대 자체는 무엇이든 상관없다. 코드가 KST 를 직접 지정한다.
- **systemd 가 있어야 `deploy/gpu-reserve.service` 를 그대로 쓸 수 있다.**
  없는 환경이면 같은 `ExecStart` 명령을 다른 방식(supervisor, tmux 등)으로 실행한다.
- **서비스 파일 안에 사용자와 절대경로가 박혀 있다.** 아래 5곳을 모두 설치 환경에 맞게 고친다.
  (자세한 내용은 4-6)
  `User=` / `Group=` / `WorkingDirectory=` / `Environment=GPU_RESERVE_CONFIG=` / `ExecStart=`
- **Node.js 는 화면 빌드에만 쓰인다.** 서버에 설치하기 어렵다면 다른 컴퓨터에서 `npm run build` 로
  만든 `frontend/dist` 폴더를 통째로 복사해도 된다. 운영 중에는 Node 가 필요 없다.
- **백업 crontab 의 경로**도 새 설치 경로·계정에 맞게 다시 등록한다. (7장)
- DB 는 빈 상태로 새로 시작하거나, 기존 DB 파일을 복사해 올 수 있다. (9장)

---

## 2. 포트

| 포트 | 용도 | 비고 |
|---|---|---|
| **9080** | 운영 서버 (화면 + API) | 접속 주소: `http://<서버IP>:9080` |
| 9081 | 개발용 백엔드 | 개발할 때만 사용 |
| 5173 | Vite 개발 서버 (화면) | 개발할 때만 사용, `/api` 요청을 9081 로 전달 |

- 외부에 열어야 할 포트는 **9080** 하나다. 9081, 5173 은 열 필요 없다.
- 포트를 바꾸려면 `deploy/gpu-reserve.service` 의 `ExecStart=` 를 고친다.
  개발용 포트를 바꾸면 `frontend/vite.config.js` 의 proxy target 도 같이 고친다.
- 운영 사이트는 **한 대의 컴퓨터에서만** 켠다. DB 가 컴퓨터마다 따로 있어서,
  두 곳에서 동시에 운영하면 겹침 검사가 무의미해진다.
- 서버 IP 확인: `ip -4 addr show scope global | grep inet`

---

## 3. 운영과 개발

| | 운영 | 개발 |
|---|---|---|
| 실행 | systemd (항상 켜짐) | 터미널에서 직접 |
| 포트 | 9080 | 9081 + 5173 |
| 설정 파일 | `backend/config.yaml` | `backend/config.dev.yaml` |
| DB | `data/gpu.db` (실제 데이터) | `backend/dev/dev.db` |
| 화면 | 빌드 결과(`frontend/dist`)를 백엔드가 서빙 | Vite 가 직접 서빙 |

- 개발 명령에는 항상 `GPU_RESERVE_CONFIG=config.dev.yaml` 을 붙인다. 빠뜨리면 운영 DB 를 쓰게 된다.
- 운영 서버가 `frontend/dist` 를 그대로 서빙하므로, 운영 중인 컴퓨터에서 개발 목적으로
  `npm run build` 를 실행하면 운영 화면이 즉시 바뀐다. 빌드는 배포할 때만 한다.

### PYTHONPATH

이 프로젝트의 파이썬 명령에는 `PYTHONPATH=` 를 붙인다.
`PYTHONPATH` 에 다른 경로(예: ROS 의 `/opt/ros/...`)가 들어 있으면 파이썬이 엉뚱한 모듈을 읽어
pytest 나 서버가 오류를 낸다. 빈 값으로 덮어써서 이를 막는다.
`deploy/gpu-reserve.service` 와 `deploy/backup_db.sh` 에도 같은 설정이 들어 있다.

---

## 4. 설치

아래 명령은 저장소 경로를 `/home/<사용자>/GPU_server_reservation_ws` 로 가정한다.

### 4-1. 패키지

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git cron tzdata
```

Node.js (화면을 이 컴퓨터에서 빌드할 경우):

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
```

### 4-2. 코드 받기

```bash
git clone git@github.com:foodbanana/GPU_server_reservation.git ~/GPU_server_reservation_ws
```

### 4-3. 백엔드

```bash
cd ~/GPU_server_reservation_ws/backend
python3 -m venv venv
PYTHONPATH= venv/bin/pip install --upgrade pip
PYTHONPATH= venv/bin/pip install -r requirements.txt
```

### 4-4. 설정 파일

```bash
cd ~/GPU_server_reservation_ws/backend
cp config.example.yaml config.yaml
PYTHONPATH= venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`config.yaml` 에서 아래 두 값을 채운다. 비어 있으면 서버가 시작되지 않는다.

```yaml
app:
  invite_code: "연구실 가입 코드"
  jwt_secret: "위에서 출력된 문자열"
```

- `config.yaml` 은 `.gitignore` 에 있어 git 에 올라가지 않는다. 서버를 옮길 때는 직접 복사해야 한다.
- `database_path`, `static_dir` 는 **이 설정 파일 위치 기준 상대경로**로 해석된다.
  기본값(`../data/gpu.db`, `../frontend/dist`)을 그대로 두면 저장소를 어디에 두든 동작한다.
- GPU 모델명과 단주기/장주기 분류(`category: short | long`)는 같은 파일의 `gpus:` 에서 수정한다.
  서버를 켤 때마다 이 목록대로 DB 의 GPU 정보를 맞춘다.

### 4-5. 화면 빌드

```bash
cd ~/GPU_server_reservation_ws/frontend
npm install
npm run build
```

`frontend/dist/index.html` 이 생기면 된다. 이 폴더가 없으면 API 는 동작하지만 화면 대신 안내 메시지가 나온다.

### 4-6. 서비스 등록

`deploy/gpu-reserve.service` 안의 사용자와 **절대경로 5곳**을 먼저 고친다.

| 항목 | 저장소의 현재 값 | 고칠 내용 |
|---|---|---|
| `User=` / `Group=` | `taeung` | 서버를 실행할 계정 (root 로 돌리지 않는다) |
| `WorkingDirectory=` | `/home/taeung/GPU_server_reservation_ws/backend` | 새 설치 경로의 `backend` |
| `Environment=GPU_RESERVE_CONFIG=` | `/home/taeung/.../backend/config.yaml` | 새 설치 경로의 `config.yaml` (절대경로) |
| `ExecStart=` | `/home/taeung/.../backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 9080` | venv 파이썬 경로, 필요하면 포트 |

`Environment=PYTHONPATH=` 와 `Environment=PYTHONUNBUFFERED=1`, `Restart=always` 는 그대로 둔다.

```bash
cd ~/GPU_server_reservation_ws
sudo cp deploy/gpu-reserve.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gpu-reserve
```

확인:

```bash
systemctl status gpu-reserve
curl http://localhost:9080/api/health     # {"status":"ok"}
```

서비스 파일을 고칠 때마다 **복사 → `daemon-reload` → `restart`** 세 단계를 모두 실행해야 반영된다.

### 4-7. 관리자 계정

브라우저에서 평소처럼 회원가입한 뒤 그 계정을 관리자로 올리는 방법을 권장한다.

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/create_admin.py --email 관리자이메일@example.com
```

- 이미 가입한 이메일이면 **계정을 새로 만들지 않고 관리자로 승격**한다. (이름·비밀번호는 그대로)
- 가입한 적 없는 이메일이면 이름과 비밀번호를 물어보고 새 관리자 계정을 만든다.
  이름은 `--name 홍길동` 으로 미리 줄 수도 있다. `--email` 을 생략하면 이메일부터 물어본다.
- 이미 로그인 중이었다면 **로그아웃 후 다시 로그인**해야 관리자 메뉴가 보인다.

---

## 5. 서비스 관리

| 작업 | 명령 |
|---|---|
| 상태 | `systemctl status gpu-reserve` |
| 시작 | `sudo systemctl start gpu-reserve` |
| 중지 | `sudo systemctl stop gpu-reserve` |
| 재시작 | `sudo systemctl restart gpu-reserve` |
| 부팅 시 자동 시작 켜기 / 끄기 | `sudo systemctl enable gpu-reserve` / `disable` |
| 자동 시작 여부 확인 | `systemctl is-enabled gpu-reserve` |

프로세스가 비정상 종료되면 systemd 가 5초 뒤 자동으로 다시 켠다. (`Restart=always`)

### 로그

```bash
journalctl -u gpu-reserve -f              # 실시간
journalctl -u gpu-reserve -n 100          # 최근 100줄
journalctl -u gpu-reserve --since today   # 오늘
journalctl -u gpu-reserve -p err          # 오류만
```

---

## 6. 코드 변경 반영

```bash
cd ~/GPU_server_reservation_ws
./deploy/backup_db.sh
git pull
(cd frontend && npm install && npm run build)
(cd backend && PYTHONPATH= venv/bin/pip install -r requirements.txt)
(cd backend && PYTHONPATH= venv/bin/python -m pytest)
sudo systemctl restart gpu-reserve
curl http://localhost:9080/api/health
```

| 변경한 곳 | 빌드 | pip install | 재시작 |
|---|---|---|---|
| `frontend/` | 필요 | - | 불필요 (브라우저 Ctrl+Shift+R) |
| `backend/` 코드 | - | - | 필요 |
| `backend/requirements.txt` | - | 필요 | 필요 |
| `backend/config.yaml` | - | - | 필요 |
| `deploy/gpu-reserve.service` | - | - | 복사 + `daemon-reload` + 재시작 |

- 운영 서버는 `--reload` 없이 실행되므로 백엔드 코드 변경은 재시작해야 반영된다.
- `config.yaml` 은 서버를 켤 때 한 번만 읽는다. 값이 잘못되면 서비스가 아예 시작되지 않으므로
  재시작 후 `journalctl -u gpu-reserve -n 30` 으로 확인한다.

---

## 7. 백업

예약 데이터는 `data/gpu.db` 파일 하나에 들어 있다.

### 수동 백업

```bash
~/GPU_server_reservation_ws/deploy/backup_db.sh
```

- SQLite 온라인 백업 API 를 쓰므로 **서비스가 켜진 상태에서도 안전하다.** (`cp` 로 직접 복사하지 않는다)
- 복사 후 `PRAGMA integrity_check` 로 검사하고, 통과했을 때만 최종 파일 이름으로 바꾼다.
  중간에 실패하면 `.tmp` 만 남고 이전 백업은 보존된다.
- 결과: `~/gpu-reserve-backups/gpu_YYYY-MM-DD.db` (같은 날 다시 돌리면 덮어쓴다)
- 30일 지난 백업은 자동 삭제된다.
- 실행 기록: `~/gpu-reserve-backups/backup.log`

### 자동 백업 (매일 04:00)

crontab 은 **서비스 실행 계정으로, `sudo` 없이** 등록한다.
로그 리디렉션 때문에 백업 폴더가 미리 있어야 하므로, **수동 백업을 한 번 먼저 실행한다.**

```bash
~/GPU_server_reservation_ws/deploy/backup_db.sh      # 폴더 생성 겸 동작 확인
(crontab -l 2>/dev/null; echo "0 4 * * * /home/<사용자>/GPU_server_reservation_ws/deploy/backup_db.sh >> /home/<사용자>/gpu-reserve-backups/cron.log 2>&1") | crontab -
crontab -l
```

- 위 등록 명령은 한 번만 실행한다. 여러 번 실행하면 같은 작업이 중복 등록된다.
- `0 4 * * *` = 매일 04:00 (분 시 일 월 요일).
- 컴퓨터가 꺼져 있거나 절전 상태면 실행되지 않는다. (10장)

### 백업 위치 변경

```bash
cp deploy/backup.conf.example deploy/backup.conf
```

`deploy/backup.conf` 에서 `BACKUP_DIR`, `KEEP_DAYS` 를 수정한다. 외장 디스크나 NAS 는 미리 마운트되어 있어야 한다.
한 번만 다른 곳에 저장하려면 환경변수로도 된다. (환경변수 > `backup.conf` > 기본값 순으로 우선)

```bash
BACKUP_DIR=/mnt/usb ~/GPU_server_reservation_ws/deploy/backup_db.sh
```

---

## 8. 복구

```bash
sudo systemctl stop gpu-reserve

cd ~/GPU_server_reservation_ws/data
mv gpu.db gpu.db.broken-$(date +%Y%m%d-%H%M)
mv gpu.db-wal gpu.db-wal.old 2>/dev/null
mv gpu.db-shm gpu.db-shm.old 2>/dev/null

ls -lh ~/gpu-reserve-backups/
cp ~/gpu-reserve-backups/gpu_YYYY-MM-DD.db ~/GPU_server_reservation_ws/data/gpu.db

sudo systemctl start gpu-reserve
```

`gpu.db-wal`, `gpu.db-shm` 은 이전 DB 의 보조 파일이다. 남겨 두면 복구한 DB 와 섞이므로 반드시 치운다.
복구한 파일의 소유자가 서비스 실행 계정인지 확인한다. (`ls -l`)

---

## 9. DB 이전 및 초기화

### 다른 컴퓨터의 DB 가져오기

1. 기존 서버에서 `deploy/backup_db.sh` 실행 → `~/gpu-reserve-backups/gpu_YYYY-MM-DD.db` 생성
2. 그 파일을 새 서버로 복사
3. 새 서버의 서비스를 중지하고 `data/gpu.db` 로 복사 (8장과 같은 절차) 후 시작

계정·비밀번호·예약이 모두 그대로 넘어간다.
`config.yaml` 의 `jwt_secret` 이 기존 서버와 다르면 사용자들은 다시 로그인해야 한다.

### 빈 DB로 시작

```bash
sudo systemctl stop gpu-reserve
~/GPU_server_reservation_ws/deploy/backup_db.sh
rm -f ~/GPU_server_reservation_ws/data/gpu.db ~/GPU_server_reservation_ws/data/gpu.db-wal ~/GPU_server_reservation_ws/data/gpu.db-shm
sudo systemctl start gpu-reserve
```

서비스가 시작되면 빈 DB 와 `config.yaml` 의 GPU 목록이 자동으로 만들어진다.
이후 회원가입과 관리자 계정 생성을 다시 한다. (4-7)

---

## 10. 서버 환경 설정

### 절전 모드 (데스크탑 환경이 설치된 경우)

절전 상태에서는 접속도 자동 백업도 되지 않는다.

```bash
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

되돌리기:

```bash
gsettings reset org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type
sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

### 방화벽 (ufw)

```bash
sudo ufw status
```

- `inactive` 면 추가 설정이 필요 없다.
- `active` 면 `sudo ufw allow 9080/tcp`
- 방화벽을 새로 켤 때는 **SSH 포트를 먼저 연다.** (원격 접속이 끊길 수 있다)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 9080/tcp
sudo ufw enable
```

---

## 11. 문제 해결

### 접속이 안 될 때

```bash
systemctl status gpu-reserve              # 서비스 상태
curl http://localhost:9080/api/health     # 서버 내부 응답
ip -4 addr show scope global | grep inet  # IP 변경 여부
sudo ufw status                           # 방화벽
```

서버 내부에서 `{"status":"ok"}` 가 나오면 서버는 정상이고 네트워크(IP 변경, 방화벽) 문제다.
학교 내부망 밖(LTE 등)에서는 접속되지 않는다.

### 서비스가 시작되지 않을 때

```bash
journalctl -u gpu-reserve -n 50 --no-pager
```

| 로그 메시지 | 원인 | 조치 |
|---|---|---|
| `Address already in use` | 9080 포트를 다른 프로그램이 쓰고 있다 | `ss -tlnp \| grep 9080` 으로 확인 후 정리 |
| `설정 파일이 없습니다: <경로>` | `config.yaml` 이 없거나 서비스 파일의 `GPU_RESERVE_CONFIG` 경로가 틀렸다 | 4-4 / 4-6 |
| `... 의 app.invite_code 값이 비어 있습니다` | 설정값을 채우지 않았다 (`jwt_secret` 도 같은 형태) | `config.yaml` 수정 후 재시작 |
| `... 의 gpus 목록이 비어 있습니다` | `config.yaml` 의 `gpus:` 가 비었다 | `config.example.yaml` 참고해 채우기 |
| `GPU 설정의 category 는 short 또는 long 이어야 합니다` | `category` 오타 | `short` / `long` 으로 수정 |
| `ModuleNotFoundError` | 라이브러리 누락 또는 `PYTHONPATH` 오염 | `pip install -r requirements.txt`, 서비스 파일의 `Environment=PYTHONPATH=` 확인 |
| `status=217/USER` | 서비스 파일의 `User=` 계정이 없다 | `User=` / `Group=` 수정 → 복사 → `daemon-reload` |
| `status=200/CHDIR` 또는 `203/EXEC` | `WorkingDirectory=` / `ExecStart=` 경로가 틀렸다 | 경로 수정 → 복사 → `daemon-reload` |

### 서비스는 켜졌는데 화면 대신 안내 메시지가 나올 때

`/` 접속 시 HTTP 503 과 함께 `화면(프론트엔드) 빌드 결과를 찾지 못했습니다` 가 나오면
`frontend/dist` 가 없는 것이다. 서비스는 정상이고 API 만 동작하는 상태다.

```bash
cd ~/GPU_server_reservation_ws/frontend && npm install && npm run build
sudo systemctl restart gpu-reserve
```

`이 서버는 API만 제공합니다(개발용 설정)` 이 나오면 운영 서비스가 개발용 설정(`config.dev.yaml`)을
읽고 있는 것이다. 서비스 파일의 `GPU_RESERVE_CONFIG` 경로를 확인한다.

### 로그인 상태가 이상할 때

브라우저 개발자도구(F12) → Application → Local Storage → `gpu-reserve-token` 삭제 후 새로고침.

### 비밀번호를 잊은 사용자가 있을 때

이메일로 찾는 기능은 없다. 서버에서 직접 재설정한다. (12장)

---

## 12. 계정 관리 명령

운영 DB 를 대상으로 하며, 서비스를 켜 둔 채 실행해도 된다. 모두 `backend` 폴더에서 실행한다.

```bash
cd ~/GPU_server_reservation_ws/backend

# 관리자 생성 또는 기존 가입자 승격 (--name 은 새로 만들 때만 쓰인다)
PYTHONPATH= venv/bin/python scripts/create_admin.py --email someone@example.com --name 홍길동

# 관리자 권한 부여 / 해제 / 목록
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com --revoke
PYTHONPATH= venv/bin/python scripts/set_admin.py --list

# 비밀번호 재설정 (새 비밀번호를 두 번 입력받는다)
PYTHONPATH= venv/bin/python scripts/reset_password.py someone@example.com
```

- **마지막 남은 관리자의 권한은 해제할 수 없다.** 다른 사람을 먼저 관리자로 지정한 뒤 해제한다.
- 가입한 적 없는 이메일에 `set_admin.py` / `reset_password.py` 를 쓰면
  `가입된 적 없는 이메일입니다` 오류만 내고 아무것도 바꾸지 않는다.
  계정까지 새로 만들려면 `create_admin.py` 를 쓴다.
- 권한을 바꾼 뒤에는 그 사용자가 다시 로그인해야 화면에 반영된다.

---

## 13. 개발

운영 서버(9080)는 켜 둔 채로 작업한다.

### 최초 1회

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/init_dev.py
```

`config.dev.yaml` 과 개발용 DB 폴더(`backend/dev/`)를 만든다. 개발용 가입 코드는 `DEV-CODE-1234`.
개발용 설정은 화면을 서빙하지 않고 API 만 제공한다. (화면은 Vite 가 맡는다)

### 실행

터미널 1 — 개발용 백엔드 (9081):

```bash
cd ~/GPU_server_reservation_ws/backend
GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= venv/bin/python -m uvicorn app.main:app --reload --port 9081
```

터미널 2 — 화면 (5173):

```bash
cd ~/GPU_server_reservation_ws/frontend
npm run dev
```

브라우저: `http://localhost:5173` (API 문서: `http://localhost:9081/docs`)
개발 DB 를 비우려면 `rm -f backend/dev/dev.db*`.

### 테스트

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python -m pytest
```

테스트는 매번 임시 폴더에 새 DB 를 만들어 쓴다. 운영·개발 DB 를 건드리지 않는다.

---

## 14. 폴더 구조

```
GPU_server_reservation_ws/
├── README.md                설치·운영 안내 (이 문서)
├── SPEC.md                  요구사항
├── PLAN.md                  설계
├── backend/
│   ├── config.yaml          운영 설정 (git 제외, 직접 복사 필요)
│   ├── config.dev.yaml      개발 설정 (git 제외, init_dev.py 가 생성)
│   ├── config.example.yaml  설정 예시
│   ├── requirements.txt     파이썬 라이브러리 목록
│   ├── app/                 서버 코드
│   ├── scripts/             관리자·비밀번호·개발환경·데모 스크립트
│   ├── tests/               테스트
│   ├── dev/                 개발용 DB (git 제외)
│   └── venv/                파이썬 가상환경 (git 제외)
├── frontend/
│   ├── src/                 화면 코드
│   ├── public/images/       로고
│   ├── vite.config.js       개발 서버 포트·proxy 설정
│   └── dist/                빌드 결과, 운영에서 서빙 (git 제외)
├── deploy/
│   ├── gpu-reserve.service  systemd 서비스 (사용자·경로 수정 필요)
│   ├── backup_db.sh         DB 백업
│   └── backup.conf.example  백업 설정 예시
└── data/
    └── gpu.db               운영 DB (git 제외, 백업 대상)
```

git 에 올라가지 않는 것: `backend/config.yaml`, `backend/config.dev.yaml`, `backend/secrets/`,
`data/*.db`, `backend/venv/`, `node_modules/`, `frontend/dist/`, `backend/dev/`, `backend/demo/`,
`deploy/backup.conf`.
**서버를 옮길 때는 `config.yaml` 과 `data/gpu.db` 를 따로 챙겨야 한다.**
