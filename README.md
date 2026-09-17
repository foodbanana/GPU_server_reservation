# 연구실 GPU 예약 시스템

연구실 GPU 서버 3대(GPU 12장)를 겹치지 않게 예약하고, 2주치 예약 현황을 시간표로 보는 웹 서비스.
예약 시간 길이·기간 제한은 없다(연구실에서 협의해 사용). 시간표의 **이전/다음 2주** 버튼으로 더 먼 미래도 볼 수 있다.

- 접속 주소: **http://143.248.247.93:9080** (이 데스크탑의 현재 IP. 바뀌면 아래 [IP 확인](#부록-1-내-데스크탑-ip-확인) 참고)
  - 포트가 예전에는 8000 이었다. 이 컴퓨터에서 **강화학습·VLA 추론 서버가 8000번대를 쓸 수 있어서**
    충돌을 피하려고 **9080** 으로 옮겼다. (개발용 백엔드도 8001 → **9081**)
- PC와 휴대폰 브라우저에서 모두 쓸 수 있다. (학교 내부망 안에서만)
- 데스크탑을 껐다 켜도 자동으로 다시 시작된다.

> 이 문서는 **웹 개발을 처음 하는 사람 기준**으로 썼다.
> 명령어는 위에서부터 순서대로 복사해서 붙여 넣으면 된다.
> `sudo` 가 붙은 명령은 비밀번호를 물어본다. 이 컴퓨터 로그인 비밀번호를 입력하면 된다.

---

## 목차

1. [먼저 알아 둘 것 — 운영과 개발은 다르다](#1-먼저-알아-둘-것--운영과-개발은-다르다)
2. [처음 설치](#2-처음-설치)
3. [서비스 등록하고 켜기](#3-서비스-등록하고-켜기)
4. [평소에 쓰는 명령 — 시작·중지·재시작·상태](#4-평소에-쓰는-명령--시작중지재시작상태)
5. [로그 보기](#5-로그-보기)
6. [코드를 고친 뒤 운영 서버에 반영하기](#6-코드를-고친-뒤-운영-서버에-반영하기)
7. [설정(config.yaml)을 바꿨을 때](#7-설정configyaml을-바꿨을-때)
8. [DB 백업](#8-db-백업)
9. [백업에서 복구하기](#9-백업에서-복구하기)
10. [절전 모드 끄기 (중요)](#10-절전-모드-끄기-중요)
11. [방화벽(ufw) 확인](#11-방화벽ufw-확인)
12. [운영 시작 전 테스트 데이터 정리](#12-운영-시작-전-테스트-데이터-정리)
13. [문제가 생겼을 때](#13-문제가-생겼을-때)
14. [개발할 때 (코드 고칠 때)](#14-개발할-때-코드-고칠-때)

---

## 1. 먼저 알아 둘 것 — 운영과 개발은 다르다

이 시스템은 **두 가지 모드**로 돌릴 수 있다. 섞어 쓰면 진짜 예약 데이터가 망가질 수 있으니 구분해서 기억한다.

| | **운영 (실제 서비스)** | **개발 (코드 고칠 때)** |
|---|---|---|
| 누가 켜나 | systemd 가 알아서 (항상 켜져 있음) | 내가 터미널에서 직접 |
| 포트 | **9080** | 백엔드 **9081** + 화면 **5173** |
| DB 파일 | `data/gpu.db` ← **진짜 데이터** | `backend/dev/dev.db` (연습용) |
| 설정 파일 | `backend/config.yaml` | `backend/config.dev.yaml` |
| 화면 | FastAPI 가 빌드 결과를 같이 내보냄 | vite 가 따로 내보냄 (고치면 바로 반영) |
| 접속 주소 | http://143.248.247.93:9080 | http://localhost:5173 |

**핵심:** 개발용 명령은 `data/gpu.db` 를 절대 건드리지 않는다. 개발하려고 운영 서버를 끌 필요도 없다.
둘은 포트도 DB도 다르므로 **동시에 켜 놔도 된다.**

용어 두 개만:

- **백엔드(backend)**: 데이터를 저장하고 규칙을 검사하는 쪽. 파이썬으로 만들었다.
- **프론트엔드(frontend)**: 브라우저에 보이는 화면. Vue 로 만들었고, `npm run build` 로 **완성된 파일**을 만들어 둔다.
  운영에서는 이 완성된 파일을 백엔드가 같이 내보내기 때문에 **프로그램 하나, 포트 하나**로 끝난다.

---

## 2. 처음 설치

이 컴퓨터에 처음 설치할 때 **한 번만** 하면 된다.

### 2-1. 필요한 프로그램 확인

```bash
python3 --version      # 3.10 이상
node --version         # v24 이상
npm --version
systemctl --version
crontab -l             # "no crontab for taeung" 이라고 나와도 정상 (cron 이 깔려 있다는 뜻)
```

없다고 나오면 (사용자가 직접 실행):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git cron ufw
```

Node.js 가 없거나 버전이 낮으면:

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2-2. 백엔드 준비

```bash
cd ~/GPU_server_reservation_ws/backend
python3 -m venv venv
PYTHONPATH= venv/bin/pip install -r requirements.txt
```

> **`PYTHONPATH=` 는 왜 붙이나?**
> 이 컴퓨터에는 ROS(로봇 소프트웨어)가 깔려 있어서, 파이썬이 엉뚱한 폴더를 먼저 뒤지다가 오류를 낸다.
> `PYTHONPATH=` 는 "그 폴더 목록을 이번 명령에서만 비워라" 라는 뜻이다. **이 프로젝트의 파이썬 명령에는 항상 붙인다.**

### 2-3. 설정 파일 만들기

```bash
cd ~/GPU_server_reservation_ws/backend
cp config.example.yaml config.yaml

# JWT 비밀키로 쓸 긴 임의 문자열 만들기 (아래 출력값을 복사해 둔다)
PYTHONPATH= venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

그다음 `config.yaml` 을 열어서(`nano config.yaml` 또는 텍스트 편집기) 두 줄을 채운다.

```yaml
app:
  invite_code: "연구실원에게만 알려 줄 가입 코드"   # 이걸 모르면 회원가입을 못 한다
  jwt_secret: "위에서 만든 긴 문자열 붙여넣기"
```

- `config.yaml` 은 비밀값이 들어 있어서 **git 에 올라가지 않는다.**
- GPU 모델 이름이나 서버 3의 A100/maxQ 번호가 실제와 다르면 같은 파일의 `gpus:` 부분만 고치면 된다.

### 2-4. 화면 빌드

```bash
cd ~/GPU_server_reservation_ws/frontend
npm install
npm run build
```

`frontend/dist` 폴더가 생기면 성공이다. 이 폴더를 백엔드가 같이 내보낸다.

### 2-5. 관리자 계정 만들기

먼저 서비스를 켠 뒤([3장](#3-서비스-등록하고-켜기)) 브라우저에서 평소처럼 **회원가입**을 하고, 그 계정을 관리자로 올리는 방법을 추천한다.

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/set_admin.py 내이메일@example.com
```

가입도 같이 하고 싶으면:

```bash
PYTHONPATH= venv/bin/python scripts/create_admin.py
```

> 관리자 권한을 준 뒤에는 **로그아웃했다가 다시 로그인**해야 화면에 `관리자` 메뉴가 보인다.

---

## 3. 서비스 등록하고 켜기

여기서 말하는 "서비스"는 **터미널을 닫아도 계속 돌고, 컴퓨터를 껐다 켜도 자동으로 시작되는 프로그램**이다.
우분투의 `systemd` 가 관리해 준다.

### 3-1. 미리 확인할 것

이미 9080 포트로 직접 켜 둔 서버(`uvicorn ...`)가 있으면 **먼저 그 터미널에서 `Ctrl+C` 로 끈다.**
포트는 프로그램 하나만 쓸 수 있어서, 안 끄면 서비스가 "Address already in use" 오류로 죽는다.

지금 9080 포트를 누가 쓰고 있는지 확인:

```bash
ss -tlnp | grep 9080      # 아무것도 안 나오면 비어 있는 것
```

### 3-2. 등록 (사용자가 직접 실행)

```bash
sudo cp /home/taeung/GPU_server_reservation_ws/deploy/gpu-reserve.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gpu-reserve
```

- `enable` = 부팅할 때 자동 시작하도록 등록
- `--now` = 지금 바로 켜기

### 3-3. 잘 켜졌는지 확인

```bash
systemctl status gpu-reserve
```

초록색 `active (running)` 이 보이면 성공이다. (`q` 를 누르면 빠져나온다)

```bash
curl http://localhost:9080/api/health     # {"status":"ok"} 가 나오면 정상
```

이제 브라우저에서 **http://143.248.247.93:9080** 으로 들어가면 화면이 보인다.
휴대폰도 같은 와이파이(학교 내부망)에서 같은 주소로 들어가면 된다.

### 3-4. 재부팅 후에도 되는지 확인 (한 번은 해 볼 것)

```bash
sudo reboot
```

다시 켜진 뒤, 아무 명령도 하지 말고 휴대폰에서 바로 http://143.248.247.93:9080 에 들어가 본다.
화면이 보이고 예약이 되면 배포 완료다.

---

## 4. 평소에 쓰는 명령 — 시작·중지·재시작·상태

| 하고 싶은 것 | 명령 |
|---|---|
| 상태 보기 | `systemctl status gpu-reserve` |
| 시작 | `sudo systemctl start gpu-reserve` |
| 중지 | `sudo systemctl stop gpu-reserve` |
| **재시작** (제일 자주 씀) | `sudo systemctl restart gpu-reserve` |
| 부팅 시 자동 시작 켜기 | `sudo systemctl enable gpu-reserve` |
| 부팅 시 자동 시작 끄기 | `sudo systemctl disable gpu-reserve` |
| 자동 시작이 켜져 있나 확인 | `systemctl is-enabled gpu-reserve` |

- **중지하면 예약 화면이 접속되지 않는다.** 데이터가 지워지는 것은 아니다.
- 프로그램이 오류로 죽으면 systemd 가 5초 뒤에 **알아서 다시 켠다.**

---

## 5. 로그 보기

로그 = 서버가 남긴 기록. 문제가 생기면 여기부터 본다.

```bash
# 실시간으로 계속 보기 (Ctrl+C 로 빠져나옴) — 제일 자주 쓴다
journalctl -u gpu-reserve -f

# 최근 100줄만
journalctl -u gpu-reserve -n 100

# 오늘 것만
journalctl -u gpu-reserve --since today

# 오류만 골라 보기
journalctl -u gpu-reserve -p err
```

정상일 때는 접속할 때마다 `INFO: ... "GET /api/gpus HTTP/1.1" 200 OK` 같은 줄이 올라간다.
`Traceback` 이라는 단어가 보이면 그 아래가 오류 내용이다.

---

## 6. 코드를 고친 뒤 운영 서버에 반영하기

코드를 고쳤다고 해서 운영 서버에 바로 반영되지 않는다. (운영은 일부러 `--reload` 를 쓰지 않는다.
사용 중에 서버가 제멋대로 재시작되면 안 되기 때문이다.)

**순서대로** 실행한다:

```bash
cd ~/GPU_server_reservation_ws

# 0) 혹시 모르니 먼저 백업
./deploy/backup_db.sh

# 1) 새 코드 받기
git pull

# 2) 화면을 고쳤다면 다시 빌드 (frontend/ 안의 파일이 바뀌었을 때)
cd frontend && npm install && npm run build && cd ..

# 3) 파이썬 라이브러리가 추가됐다면 설치 (backend/requirements.txt 가 바뀌었을 때)
cd backend && PYTHONPATH= venv/bin/pip install -r requirements.txt && cd ..

# 4) 테스트가 통과하는지 확인 (운영 DB를 건드리지 않고 임시 DB로 돈다)
cd backend && PYTHONPATH= venv/bin/python -m pytest && cd ..

# 5) 서버 재시작
sudo systemctl restart gpu-reserve

# 6) 확인
systemctl status gpu-reserve
curl http://localhost:9080/api/health
```

**어디까지 해야 하나 (헷갈릴 때):**

| 무엇을 고쳤나 | 다시 빌드 | pip install | 재시작 |
|---|---|---|---|
| `frontend/` 안의 화면 | ✅ 필요 | — | ✅ 필요 없음\* |
| `backend/` 안의 파이썬 코드 | — | — | ✅ 필요 |
| `backend/requirements.txt` | — | ✅ 필요 | ✅ 필요 |
| `backend/config.yaml` | — | — | ✅ 필요 |

\* 화면만 다시 빌드한 경우 서버를 재시작하지 않아도 새 화면이 나간다.
다만 브라우저가 옛날 화면을 기억하고 있을 수 있으니, 안 바뀌어 보이면 **Ctrl+Shift+R** (강력 새로고침)을 누른다.
헷갈리면 그냥 재시작해도 아무 문제 없다.

---

## 7. 설정(config.yaml)을 바꿨을 때

`backend/config.yaml` 은 서버가 **켜질 때 한 번만** 읽는다.
그래서 가입 코드, 예약 규칙(`slot_minutes`, `timeline_days`), GPU 모델 이름 등을 바꿨으면 **반드시 재시작해야 반영된다.**

```bash
sudo systemctl restart gpu-reserve
```

- GPU 목록(`gpus:`)을 바꾸면 재시작할 때 DB 의 GPU 정보도 함께 갱신된다.
  (모델명·단주기/장주기 분류는 갱신되고, 기존 예약은 그대로 남는다)
- 설정 파일에 오타가 있으면 서버가 켜지지 않는다. `journalctl -u gpu-reserve -n 30` 으로 이유를 확인한다.

---

## 8. DB 백업

예약 데이터는 `data/gpu.db` 파일 하나에 다 들어 있다. 이 파일만 있으면 언제든 되살릴 수 있다.

### 8-1. 지금 바로 한 번 백업하기

```bash
~/GPU_server_reservation_ws/deploy/backup_db.sh
```

- **서버를 끄지 않아도 된다.** SQLite 가 공식으로 제공하는 "온라인 백업" 방식이라,
  예약이 들어오는 중에 실행해도 깨지지 않은 파일이 나온다. (그냥 `cp` 로 복사하면 깨질 수 있다)
- 결과: `~/gpu-reserve-backups/gpu_2026-09-16.db` 처럼 **날짜별 파일**이 쌓인다.
- **30일 지난 백업은 자동으로 지워진다.**
- 실행 기록은 `~/gpu-reserve-backups/backup.log` 에 남는다.

확인:

```bash
ls -lh ~/gpu-reserve-backups/
cat ~/gpu-reserve-backups/backup.log
```

### 8-2. 매일 새벽에 자동 백업 (crontab 등록)

cron = 정해진 시간에 명령을 자동으로 실행해 주는 우분투 기능.

```bash
crontab -e
```

처음 실행하면 편집기를 고르라고 한다. **`1` (nano)** 를 고르면 쉽다.
열린 파일의 **맨 아래**에 다음 한 줄을 추가한다:

```
0 4 * * * /home/taeung/GPU_server_reservation_ws/deploy/backup_db.sh >> /home/taeung/gpu-reserve-backups/cron.log 2>&1
```

저장하고 나가기: **Ctrl+O → Enter → Ctrl+X**

- `0 4 * * *` = 매일 **새벽 4시 정각**. (앞부터 분, 시, 일, 월, 요일)
  새벽 2시로 바꾸고 싶으면 `0 2 * * *`.
- 등록됐는지 확인: `crontab -l`
- `sudo` 를 붙이지 않는다. 내 계정으로 등록해야 파일 권한이 맞는다.

> **주의:** 자동 백업은 데스크탑이 **켜져 있을 때만** 돈다.
> 새벽에 절전 모드로 들어가면 실행되지 않으므로 [10장 절전 모드 끄기](#10-절전-모드-끄기-중요)를 꼭 해 둔다.

### 8-3. 백업 폴더를 옮기고 싶을 때 (외장 디스크 등)

```bash
cp ~/GPU_server_reservation_ws/deploy/backup.conf.example ~/GPU_server_reservation_ws/deploy/backup.conf
nano ~/GPU_server_reservation_ws/deploy/backup.conf
```

`BACKUP_DIR` 을 원하는 경로로 바꾸면 된다. 예:

```bash
BACKUP_DIR="/media/taeung/외장디스크/gpu-reserve-backups"
KEEP_DAYS=90
```

- 외장 디스크는 **미리 꽂혀서 마운트돼 있어야** 한다. 빠져 있으면 백업이 실패하고 로그에 남는다.
- 다른 서버(NAS)로 보내고 싶으면, 그 서버를 먼저 `/mnt/...` 로 마운트한 뒤 그 경로를 적는다.
- 한 번만 다른 곳에 저장하고 싶으면 설정 파일 없이 이렇게도 된다:
  ```bash
  BACKUP_DIR=/media/taeung/usb ~/GPU_server_reservation_ws/deploy/backup_db.sh
  ```

---

## 9. 백업에서 복구하기

DB 가 망가졌거나, 실수로 데이터를 지웠을 때 되돌리는 방법이다.
**순서를 지켜야 한다. 특히 서버를 먼저 꺼야 한다.**

```bash
# 1) 서버 끄기 (켜진 채로 DB 파일을 바꾸면 안 된다)
sudo systemctl stop gpu-reserve

# 2) 지금 DB를 혹시 모르니 따로 보관해 둔다 (덮어쓰기 전에!)
cd ~/GPU_server_reservation_ws/data
mv gpu.db gpu.db.망가진것-$(date +%Y%m%d-%H%M)
mv gpu.db-wal gpu.db-wal.old 2>/dev/null
mv gpu.db-shm gpu.db-shm.old 2>/dev/null

# 3) 되돌릴 백업 파일 고르기
ls -lh ~/gpu-reserve-backups/

# 4) 그 파일을 gpu.db 로 복사 (아래 날짜는 고른 파일 이름으로 바꿀 것)
cp ~/gpu-reserve-backups/gpu_2026-09-16.db ~/GPU_server_reservation_ws/data/gpu.db

# 5) 서버 다시 켜기
sudo systemctl start gpu-reserve
systemctl status gpu-reserve
```

**2번을 건너뛰지 말 것.** `gpu.db-wal` / `gpu.db-shm` 은 옛날 DB 의 "아직 반영 안 된 메모"라서,
새 DB 옆에 남아 있으면 데이터가 이상해질 수 있다. 이름을 바꿔 치워 두면 안전하다.

복구가 잘 됐는지 확인한 뒤(브라우저에서 예약 목록 확인), 마음이 놓이면 `.망가진것-...` 파일들을 지우면 된다.

---

## 10. 절전 모드 끄기 (중요)

**지금 이 데스크탑은 일정 시간 놀면 자동으로 절전 모드(suspend)에 들어가도록 설정돼 있다.**
그러면 예약 사이트가 먹통이 되고 새벽 백업도 돌지 않는다. 24시간 켜 두는 서버이므로 **반드시 꺼야 한다.**

### 10-1. 화면으로 끄기 (제일 쉬움)

`설정(Settings)` → `전원(Power)` → **`자동 절전 모드(Automatic Suspend)` 를 끔(Off)** 으로.

### 10-2. 명령으로 끄기

```bash
# 콘센트에 꽂혀 있을 때 절전 안 함
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'

# 확인 — 'nothing' 이 나와야 한다
gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type
```

### 10-3. 확실하게 막기 (사용자가 직접 실행, 선택 사항)

시스템 차원에서 절전·최대 절전을 아예 못 하게 막는다. 서버로만 쓸 거라면 이게 제일 확실하다.

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

되돌리고 싶으면:

```bash
sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

> 모니터 화면만 꺼지는 것(화면 보호기)은 괜찮다. 서버는 계속 돈다.
> 문제가 되는 것은 **컴퓨터 자체가 자는 것(suspend)** 이다.

---

## 11. 방화벽(ufw) 확인

방화벽 = 외부에서 이 컴퓨터의 어떤 포트로 들어올 수 있는지 정하는 문지기.

```bash
sudo ufw status
```

**결과에 따라:**

- **`Status: inactive` 라고 나오면** → 방화벽이 꺼져 있다. 아무것도 안 해도 9080 포트로 접속된다.
  (현재 이 컴퓨터가 이 상태다. 학교 내부망이라 이대로 써도 된다)

- **`Status: active` 라고 나오면** → 9080 포트를 열어 줘야 한다:
  ```bash
  sudo ufw allow 9080/tcp
  sudo ufw status        # 9080/tcp ALLOW 가 보이면 성공
  ```

**방화벽을 새로 켜고 싶다면** 반드시 SSH 포트를 먼저 열고 켠다. 안 그러면 원격 접속이 끊긴다:

```bash
sudo ufw allow 22/tcp        # SSH 로 원격 접속을 쓴다면 반드시 먼저
sudo ufw allow 9080/tcp
sudo ufw enable
```

> 접속이 안 될 때 방화벽부터 의심하기 쉽지만, 대부분은 **서버가 꺼져 있거나**(`systemctl status gpu-reserve`)
> **IP 가 바뀐 것**이다. [13장](#13-문제가-생겼을-때)을 먼저 본다.

---

## 12. 운영 시작 전 테스트 데이터 정리

개발하면서 만든 연습용 계정과 예약이 `data/gpu.db` 에 들어 있다면, 진짜 운영을 시작하기 전에 한 번 비우는 게 깔끔하다.

**이건 되돌릴 수 없다.** 정말 지워도 되는지 먼저 확인한다:

```bash
# 지금 DB에 뭐가 들어 있는지 세어 보기
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python - <<'PY'
import sqlite3
db = sqlite3.connect("../data/gpu.db")
for t in ("users", "reservations"):
    print(t, db.execute(f"SELECT count(*) FROM {t}").fetchone()[0], "개")
print(db.execute("SELECT name, email, is_admin FROM users").fetchall())
PY
```

지워도 되겠다고 판단했으면:

```bash
# 1) 서버 끄기
sudo systemctl stop gpu-reserve

# 2) 만약을 위해 백업부터 (지운 뒤에 후회해도 이 파일로 되돌릴 수 있다)
~/GPU_server_reservation_ws/deploy/backup_db.sh

# 3) DB 파일 지우기 (-wal, -shm 도 같이)
cd ~/GPU_server_reservation_ws/data
rm -f gpu.db gpu.db-wal gpu.db-shm

# 4) 서버 켜기 — 빈 DB와 GPU 12장이 자동으로 다시 만들어진다
sudo systemctl start gpu-reserve
systemctl status gpu-reserve

# 5) 브라우저에서 다시 회원가입 → 관리자 권한 주기
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/set_admin.py 내이메일@example.com
```

> 계정은 남기고 예약만 지우고 싶다면 DB를 지우지 말고, 관리자 화면에서 예약을 하나씩 삭제하면 된다.

---

## 13. 문제가 생겼을 때

### 브라우저에서 접속이 안 된다

순서대로 확인한다.

```bash
# 1) 서버가 켜져 있나?
systemctl status gpu-reserve
#    active (running) 이 아니면:  sudo systemctl restart gpu-reserve

# 2) 이 컴퓨터 안에서는 되나?
curl http://localhost:9080/api/health
#    {"status":"ok"} 가 나오면 서버는 정상. 네트워크 문제다.

# 3) IP 가 바뀌지 않았나?  (제일 흔한 원인)
ip -4 addr show scope global | grep inet

# 4) 방화벽
sudo ufw status
```

휴대폰에서만 안 된다면, 휴대폰이 **학교 내부망 와이파이**에 붙어 있는지 확인한다. (LTE/5G 로는 접속되지 않는다)

### 서비스가 계속 죽는다 / 켜지지 않는다

```bash
journalctl -u gpu-reserve -n 50 --no-pager
```

자주 나오는 원인:

| 로그에 보이는 말 | 뜻 | 해결 |
|---|---|---|
| `Address already in use` | 9080 포트를 다른 프로그램이 쓰고 있다 | `ss -tlnp \| grep 9080` 으로 찾아서 그 터미널에서 Ctrl+C |
| `설정 파일이 없습니다` | `backend/config.yaml` 이 없다 | [2-3](#2-3-설정-파일-만들기) 다시 하기 |
| `app.invite_code 값이 비어 있습니다` | 설정 파일에 값을 안 채웠다 | `config.yaml` 에 가입 코드·비밀키 채우고 재시작 |
| `ModuleNotFoundError` | 라이브러리가 없다 | `cd backend && PYTHONPATH= venv/bin/pip install -r requirements.txt` 후 재시작 |

### 화면은 뜨는데 "화면 빌드 결과를 찾지 못했습니다" 라고 나온다

`npm run build` 를 안 했거나 `frontend/dist` 가 지워진 것이다.

```bash
cd ~/GPU_server_reservation_ws/frontend && npm run build
sudo systemctl restart gpu-reserve
```

### 로그인이 자꾸 풀린다 / 화면이 이상하다

브라우저에 남은 옛날 로그인 정보 때문일 수 있다.
**F12 → Application → Local Storage → `gpu-reserve-token` 삭제** 후 새로고침.

### 비밀번호를 잊은 사람이 있다

이메일로 찾는 기능은 없다. 서버에서 직접 바꿔 준다.

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/reset_password.py 그사람이메일@example.com
```

---

## 14. 개발할 때 (코드 고칠 때)

**운영 서버(9080)는 켜 둔 채로** 개발한다. 끌 필요 없다.

### 처음 한 번만

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/init_dev.py
```

개발 전용 설정(`config.dev.yaml`)과 개발 전용 DB 자리(`backend/dev/`)를 만든다.
개발용 가입 코드는 **`DEV-CODE-1234`** 다.

### 개발 중에는 터미널 2개

**터미널 1 — 개발용 백엔드 (포트 9081, 개발용 DB)**

```bash
cd ~/GPU_server_reservation_ws/backend
GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 9081
```

**터미널 2 — 화면 (포트 5173)**

```bash
cd ~/GPU_server_reservation_ws/frontend
npm run dev
```

그다음 브라우저에서 **http://localhost:5173** 접속.

- `--reload` 는 코드를 저장할 때마다 서버를 알아서 다시 켜 준다. **개발에서만** 쓴다.
- 화면에서 부르는 `/api/...` 요청은 vite 가 9081 번으로 넘겨준다 (`frontend/vite.config.js` 의 proxy).
- 개발용 DB를 비우고 싶으면: `rm -f ~/GPU_server_reservation_ws/backend/dev/dev.db*`
  (운영 DB `data/gpu.db` 와는 전혀 다른 파일이다)

### 테스트

```bash
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python -m pytest
```

테스트는 매번 **임시 폴더에 새 DB**를 만들어 쓴다. 운영 DB도 개발 DB도 건드리지 않는다.

### 다 고쳤으면

[6장 — 코드를 고친 뒤 운영 서버에 반영하기](#6-코드를-고친-뒤-운영-서버에-반영하기) 로.

---

## 부록 1. 내 데스크탑 IP 확인

```bash
ip -4 addr show scope global | grep inet
```

`inet 143.248.247.93/24` 처럼 나오는 숫자가 IP다. 접속 주소는 `http://그숫자:9080`.

IP 가 자꾸 바뀌어서 불편하면 연구실/학과 전산 담당자에게 **고정 IP** 를 요청하는 것이 가장 깔끔하다.

## 부록 2. 폴더 구조

```
GPU_server_reservation_ws/
├── README.md              ← 지금 이 문서
├── SPEC.md                요구사항
├── PLAN.md                전체 설계
├── backend/               파이썬 서버
│   ├── config.yaml        운영 설정 (비밀값 있음, git 제외)
│   ├── config.dev.yaml    개발 설정 (git 제외)
│   ├── app/               서버 코드
│   ├── scripts/           관리자 계정·비밀번호·개발환경 준비 명령
│   ├── tests/             자동 테스트
│   └── dev/               개발용 DB (git 제외)
├── frontend/              Vue 화면
│   ├── src/               화면 코드
│   └── dist/              빌드 결과 — 운영에서 실제로 서빙되는 파일 (git 제외)
├── deploy/
│   ├── gpu-reserve.service   systemd 서비스 파일
│   ├── backup_db.sh          DB 백업 스크립트
│   └── backup.conf.example   백업 설정 예시
└── data/
    └── gpu.db             ★ 진짜 예약 데이터 (git 제외, 백업 대상)
```

## 부록 3. 자주 쓰는 명령 모음

```bash
# 상태 보기
systemctl status gpu-reserve

# 재시작
sudo systemctl restart gpu-reserve

# 로그 실시간
journalctl -u gpu-reserve -f

# 백업 한 번
~/GPU_server_reservation_ws/deploy/backup_db.sh

# 관리자 권한 주기 / 목록
cd ~/GPU_server_reservation_ws/backend
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com
PYTHONPATH= venv/bin/python scripts/set_admin.py --list

# 비밀번호 재설정
PYTHONPATH= venv/bin/python scripts/reset_password.py someone@example.com

# 코드 반영 (git pull → 빌드 → 재시작)
cd ~/GPU_server_reservation_ws && git pull \
  && (cd frontend && npm install && npm run build) \
  && (cd backend && PYTHONPATH= venv/bin/pip install -r requirements.txt) \
  && sudo systemctl restart gpu-reserve
```
