# 프로젝트 작업 규칙

## 프로젝트
연구실 GPU 예약 시스템. 전체 요구사항은 `SPEC.md`에 있다. 작업 전 반드시 관련 부분을 읽는다.

## 사용자 정보
- 사용자는 웹 개발 초보자다. 설명은 한국어로, 전문 용어는 짧게 풀어서 설명한다.
- 사용자가 직접 해야 하는 작업(sudo 명령, 구글 콘솔 설정 등)은 단계별로 정확히 안내한다.

## 작업 방식
- 한 번에 요청받은 Phase만 구현한다. 다음 Phase 기능을 미리 만들지 않는다.
- 요구사항이 애매하면 추측하지 말고 먼저 질문한다.
- 각 Phase가 끝나면 다음을 알려준다:
  1. 만들거나 바꾼 파일과 각 역할
  2. 사용자가 직접 확인하는 방법 (실행 명령어, 브라우저에서 볼 것)
- SPEC.md와 다르게 구현해야 할 이유가 생기면 먼저 설명하고 동의를 받는다.

## 규칙
- 모든 시간은 Asia/Seoul 기준.
- 예약 중복 검사와 규칙 검사는 반드시 백엔드에서 한다.
- 비밀번호, 구글 credentials/토큰, .env, DB 파일은 git에 커밋하지 않는다.
- `sudo`가 필요한 명령은 직접 실행하지 말고 사용자에게 실행할 명령을 알려준다.
- 새 라이브러리를 추가하면 requirements.txt / package.json에 반영한다.
- data/ 폴더의 DB 파일은 절대 직접 삭제하거나 덮어쓰지 않는다. 테스트나 확인에는 임시 DB 경로를 사용하고, 초기화가 꼭 필요하면 먼저 사용자에게 묻는다.
- 사용자가 직접 실행 중인 서버 프로세스를 종료하지 않는다. 재시작이 필요하면 사용자에게 요청한다.
- **`frontend/dist` 를 함부로 덮어쓰지 않는다.**
  - 운영 서버가 `frontend/dist` 를 **그대로 서빙**한다. 개발 중에 `npm run build` 를 돌리면
    운영 화면이 즉시 바뀌어, 아직 반영되지 않은 백엔드와 짝이 안 맞아 오류가 난다.
  - 개발 중 화면 확인은 **vite 개발 서버(5173)** 로만 한다.
  - 빌드가 꼭 필요하면 **먼저 사용자에게 묻고** 허락을 받는다. (배포할 때만 빌드한다)
- **운영과 개발을 섞지 않는다 (Phase 5 이후).**
  - 운영: systemd 서비스 `gpu-reserve`, 포트 **9080**, 설정 `config.yaml`, DB `data/gpu.db`.
  - 개발·확인: 포트 **9081**(또는 비어 있는 다른 포트), 설정 `config.dev.yaml`, DB `backend/dev/dev.db`.
  - **8000번대 포트는 쓰지 않는다.** 이 컴퓨터에서 강화학습·VLA 추론 서버가 8000번대를 쓸 수 있어서
    충돌을 피하려고 9080/9081 로 옮겼다. (예전 포트는 8000/8001 이었다)
  - 개발용 명령에는 항상 `GPU_RESERVE_CONFIG=` 로 개발 설정을 지정한다. 안 붙이면 운영 DB를 쓰게 된다.
  - 운영 서비스를 `systemctl stop/restart` 하지 않는다. 필요하면 사용자에게 명령을 알려준다.

## 자주 쓰는 명령어

> **주의 1:** 이 컴퓨터는 ROS(`/opt/ros/jazzy`)가 `PYTHONPATH`에 들어 있어서
> pytest가 ROS 플러그인을 잘못 읽고 오류를 낸다.
> 그래서 아래 파이썬 명령에는 `PYTHONPATH=` 를 붙여 ROS 경로를 잠깐 비운다.
>
> **주의 2:** Phase 5부터 **운영 서버(포트 9080)가 systemd 로 항상 돌고 있다.**
> 개발할 때는 운영을 끄지 말고 **포트 9081 + 개발용 DB** 로 따로 띄운다.
> 초보자용 상세 안내는 `README.md` 에 있다.

| | 운영 | 개발 |
|---|---|---|
| 실행 주체 | systemd (`gpu-reserve`) | 터미널에서 직접 |
| 포트 | 9080 | 백엔드 9081 / 화면 5173 |
| 설정 | `backend/config.yaml` | `backend/config.dev.yaml` |
| DB | `data/gpu.db` (진짜 데이터) | `backend/dev/dev.db` |
| 화면 | FastAPI 가 `frontend/dist` 서빙 | vite (`npm run dev`) |

---

## 처음 한 번만 (설치)

```bash
cd backend
python3 -m venv venv
PYTHONPATH= venv/bin/pip install -r requirements.txt
cp config.example.yaml config.yaml   # 그다음 invite_code, jwt_secret 채우기
PYTHONPATH= venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"   # jwt_secret 만들기

PYTHONPATH= venv/bin/python scripts/init_dev.py   # 개발용 설정(config.dev.yaml) 만들기
```

```bash
cd frontend
npm install
```

---

## 개발 (코드 고칠 때)

운영 서버(9080)는 **켜 둔 채로** 작업한다. 터미널 2개를 띄운다.

**터미널 1 — 개발용 백엔드 (9081, 개발용 DB)**
```bash
cd backend
GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 9081
# API 직접 눌러보기: http://localhost:9081/docs
```

**터미널 2 — 화면 (5173)**
```bash
cd frontend
npm run dev        # http://localhost:5173
```

- 화면의 `/api/...` 요청은 vite 가 9081 로 넘겨준다 (`frontend/vite.config.js` 의 proxy).
- 개발용 가입 코드는 `DEV-CODE-1234` (`config.dev.yaml` 에 있음).
- 개발용 DB 비우기: `rm -f backend/dev/dev.db*` (운영 DB와 다른 파일이라 안전하다)
- **`GPU_RESERVE_CONFIG=config.dev.yaml` 을 빠뜨리면 운영 DB(`data/gpu.db`)를 쓰게 된다. 항상 붙인다.**

### 테스트 실행
테스트는 매번 임시 폴더에 새 DB를 만들어 쓴다. 운영·개발 DB를 건드리지 않는다.

```bash
cd backend
PYTHONPATH= venv/bin/python -m pytest          # 전체
PYTHONPATH= venv/bin/python -m pytest -v       # 테스트 이름까지 보기
PYTHONPATH= venv/bin/python -m pytest tests/test_overlap.py   # 파일 하나만
PYTHONPATH= venv/bin/python -m pytest tests/test_permissions.py tests/test_admin.py tests/test_accounts.py  # 권한·관리자만
PYTHONPATH= venv/bin/python -m pytest tests/test_static.py    # 빌드 화면 서빙·SPA 폴백만
```

### 휴대폰에서 확인할 때
```bash
ip -4 addr show scope global | grep inet   # 데스크탑 IP 확인
# 운영 화면: http://<데스크탑IP>:9080
# 개발 화면: http://<데스크탑IP>:5173  (npm run dev 는 기본으로 외부 접속 허용)
```
휴대폰이 없어도 PC 크롬에서 **F12 → Ctrl+Shift+M** 을 누르면 휴대폰 화면 크기로 볼 수 있다.

### 로그인이 꼬였을 때
브라우저 개발자도구(F12) → Application → Local Storage → `gpu-reserve-token` 삭제

---

## 운영 (배포된 서비스)

상세 안내는 `README.md`. `sudo` 명령은 **사용자가 직접 실행한다.**

### 서비스 다루기
```bash
systemctl status gpu-reserve              # 상태 (sudo 불필요)
journalctl -u gpu-reserve -f              # 로그 실시간 (sudo 불필요)
sudo systemctl restart gpu-reserve        # 재시작
sudo systemctl stop gpu-reserve           # 중지
```

### 운영 서버를 직접 띄워 볼 때 (서비스 등록 전 확인용)
```bash
cd backend
PYTHONPATH= venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 9080
# --reload 를 쓰지 않는다. 화면+API 가 http://<데스크탑IP>:9080 하나로 나온다.
# 이미 서비스가 켜져 있으면 포트 충돌이 나므로 먼저 서비스를 중지해야 한다.
```

### 코드 수정 → 운영 반영
```bash
cd ~/GPU_server_reservation_ws
./deploy/backup_db.sh                                    # 0) 백업
git pull                                                 # 1) 새 코드
(cd frontend && npm install && npm run build)            # 2) 화면 고쳤으면 (배포할 때만 빌드한다)
(cd backend && PYTHONPATH= venv/bin/pip install -r requirements.txt)   # 3) 라이브러리 추가했으면
(cd backend && PYTHONPATH= venv/bin/python -m pytest)    # 4) 테스트
sudo systemctl restart gpu-reserve                       # 5) 재시작
```

- **`config.yaml` 을 바꾸면 반드시 재시작해야 반영된다.** (설정은 켤 때 한 번만 읽는다)
- `frontend/` 만 고친 경우 다시 빌드하면 재시작 없이도 반영된다. (브라우저는 Ctrl+Shift+R)
  - 뒤집어 말하면 **개발 중에 빌드하면 운영 화면이 곧바로 바뀐다.** 그래서 개발 중에는 빌드하지 않는다.

### DB 백업 / 복구
```bash
./deploy/backup_db.sh                     # 지금 백업 (서버 켜진 채로 안전)
ls -lh ~/gpu-reserve-backups/             # 백업 목록 (30일치 보관)
crontab -l                                # 자동 백업 등록 확인
```
백업 폴더를 바꾸려면 `deploy/backup.conf.example` → `deploy/backup.conf` 복사 후 `BACKUP_DIR` 수정.
복구 절차(서버 중지 → 기존 DB 치우기 → 백업 복사 → 시작)는 `README.md` 9장 참고.

---

## 계정 관리 (Phase 4)

운영 DB를 대상으로 하므로 **서버는 켠 채로 실행해도 된다.**

```bash
cd backend
PYTHONPATH= venv/bin/python scripts/create_admin.py                          # 관리자 계정 만들기(대화형)
PYTHONPATH= venv/bin/python scripts/create_admin.py --email me@example.com --name 홍길동
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com         # 권한 주기
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com --revoke # 권한 뺏기
PYTHONPATH= venv/bin/python scripts/set_admin.py --list                      # 관리자 목록
PYTHONPATH= venv/bin/python scripts/reset_password.py someone@example.com    # 비밀번호 재설정
```

- `create_admin.py` 는 **이미 가입한 이메일이면 계정을 새로 만들지 않고 그 계정을 관리자로 올린다.**
  (추천: 웹에서 평소처럼 가입 → 이 명령으로 권한만 올리기)
- **마지막 남은 관리자는 해제할 수 없다.** 다른 사람을 먼저 관리자로 지정한 뒤에 해제한다.
- 관리자 권한을 준 뒤에는 **로그아웃 후 다시 로그인**해야 `관리자` 메뉴가 보인다.
- 가입한 적 없는 이메일에 `set_admin.py` / `reset_password.py` 를 쓰면 오류만 내고 아무것도 바꾸지 않는다.

---

## 타임라인 화면 확인용 데모 데이터 (Phase 3)

진짜 DB(`data/gpu.db`)도 개발 DB도 **건드리지 않는다.** `backend/demo/` 에 데모 전용 설정과 DB를 따로 만든다.
(`backend/demo/` 는 git에 올라가지 않는다)

```bash
cd backend
PYTHONPATH= venv/bin/python scripts/seed_demo.py      # 데모 DB + 예약 16건 만들기

# 데모 설정으로 서버 켜기 (포트 9081 — 9080은 운영이 쓴다)
GPU_RESERVE_CONFIG=demo/config.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 9081
```

다른 터미널에서 `cd frontend && npm run dev` → http://localhost:5173
데모 로그인: `minjun@example.com` / 비밀번호 `demo1234` (다른 계정은 스크립트 실행 결과에 나온다)
데모를 지우려면: `rm -rf backend/demo`

---

## 참고 파일

| 파일 | 역할 |
|---|---|
| `README.md` | 초보자용 설치·운영·백업·복구 안내 (사용자가 보는 문서) |
| `SPEC.md` / `PLAN.md` | 요구사항 / 전체 설계 |
| `deploy/gpu-reserve.service` | systemd 서비스 정의 (User=taeung, 자동 시작·재시작, `PYTHONPATH=`) |
| `deploy/backup_db.sh` | SQLite 온라인 백업 (서버 켜진 채로 안전), 날짜별 파일, 30일 보관 |
| `deploy/backup.conf.example` | 백업 폴더·보관 기간 설정 예시 |
| `backend/app/static_files.py` | 빌드된 화면 서빙 + 새로고침 대비 SPA 폴백 |
| `backend/scripts/init_dev.py` | 개발용 설정·DB 준비 |
