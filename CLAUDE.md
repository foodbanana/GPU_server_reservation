# 프로젝트 작업 규칙

## 프로젝트
연구실 GPU 예약 시스템. 전체 요구사항은 `SPEC.md`, 설계는 `PLAN.md`, 운영 안내는 `README.md`에 있다.
작업 전 반드시 관련 부분을 읽는다.

**현재 운영: Vercel + Neon Postgres** (서버리스). 예전의 연구실 서버 systemd 운영(포트 9080)은 쓰지 않는다.

## 사용자 정보
- 사용자는 웹 개발 초보자다. 설명은 한국어로, 전문 용어는 짧게 풀어서 설명한다.
- 사용자가 직접 해야 하는 작업(sudo 명령, Vercel·Neon·GitHub 화면 조작 등)은 단계별로 정확히 안내한다.

## 작업 방식
- 요청받은 범위만 구현한다. 다음 기능을 미리 만들지 않는다.
- 요구사항이 애매하면 추측하지 말고 먼저 질문한다.
- 작업이 끝나면 다음을 알려준다:
  1. 만들거나 바꾼 파일과 각 역할
  2. 사용자가 직접 확인하는 방법 (실행 명령어, 브라우저에서 볼 것)
- SPEC.md와 다르게 구현해야 할 이유가 생기면 먼저 설명하고 동의를 받는다.

## 운영 구조

| 조각 | 하는 일 |
|---|---|
| **GitHub** | `main` 브랜치 = **프로덕션**. main에 merge 되면 Vercel이 자동 배포한다 |
| **Vercel** | 화면(`frontend` 빌드 결과)을 내보내고, `/api/...` 는 `api/index.py` → `backend/app` (FastAPI 서버리스 함수)로 처리 |
| **Neon** | Postgres. 계정·예약 데이터. 무료 플랜은 월 100 CU-hour, 5분 동안 요청이 없어야 잠든다 |

비밀값(`DATABASE_URL`, `GPU_RESERVE_INVITE_CODE`, `GPU_RESERVE_JWT_SECRET`, `GPU_RESERVE_SUPER_ADMIN_EMAIL`)은
**Vercel 환경변수에만** 있다. 비밀이 아닌 설정(GPU 목록 등)은 `backend/config.vercel.yaml`.

## 규칙

### 기본
- 모든 시간은 Asia/Seoul 기준.
- 예약 중복 검사와 규칙 검사는 반드시 백엔드에서 한다.
- 새 라이브러리를 추가하면 `requirements.txt`(루트, Vercel용)와 `backend/requirements.txt`(로컬용)
  **둘 다** 반영한다. 두 파일은 내용이 같아야 한다. 화면 쪽은 `frontend/package.json`.

### 비밀값 — 저장소는 공개되어 있다
- 비밀번호, 토큰, `.env`, `backend/config.yaml`, DB 파일, Neon 접속 주소는 git에 커밋하지 않는다.
- 비밀값은 코드·문서·커밋 메시지에도 적지 않는다.
- Neon 대상 스크립트(`init_db.py`, `create_admin.py` 등)는 **사용자가 직접** 실행한다.
  비밀값은 사용자가 명령 앞에 직접 붙여 넣는다. Claude는 비밀값을 받아 보관하거나 대신 실행하지 않는다.

### 배포 — main 은 곧 실서비스
- `main` 에 직접 커밋·push 하지 않는다. 항상 **브랜치 → push → Preview 확인 → PR → merge** 순서.
- merge 는 사용자가 GitHub에서 한다. Claude 는 브랜치 push 까지만 한다.
- **Preview 배포도 프로덕션과 같은 Neon DB를 쓴다.** Preview에서 계정·예약을 만들거나 지우는 시험을
  하지 않는다(사용자에게도 시키지 않는다). 데이터를 바꾸는 시험은 로컬에서만 한다.
- Vercel 환경변수를 바꾸면 **Redeploy** 해야 반영된다.
- `config.vercel.yaml` 의 GPU 목록을 바꾸면 merge 후 사용자가 `scripts/init_db.py` 를 다시 실행해야 DB에 반영된다.

### DB
- **Vercel 에서는 서버를 켤 때 DB 준비(테이블 생성 등)가 자동으로 돌지 않는다.** (`api/index.py`, `app/db_init.py`)
  테이블·제약을 바꾸는 작업은 `init_db.py` 실행이 필요하고, `create_all` 은 **이미 있는 테이블의 컬럼을 바꾸지 않는다.**
  기존 테이블 구조를 바꿔야 하면(마이그레이션) 먼저 사용자와 상의한다.
- **`DATABASE_URL` 을 넣은 채 pytest 를 돌리지 않는다.** 테스트가 그 DB의 테이블을 모두 지우고 다시 만든다.
  Postgres 테스트가 꼭 필요하면 테스트 전용 DB 주소를 사용자에게 받는다.
- `data/gpu.db` 는 예전 자체 운영 시절의 데이터다. **절대 삭제하거나 덮어쓰지 않는다.**
  `backend/config.yaml` 이 이 파일을 가리키므로, `GPU_RESERVE_CONFIG` 와 `DATABASE_URL` 없이 스크립트를 돌리면 이 DB를 쓰게 된다.
- 확인·실험에는 개발 DB(`backend/dev/dev.db`)나 임시 DB(스크래치 폴더)를 쓴다. 초기화가 꼭 필요하면 먼저 묻는다.

### Neon 사용량(CU-hour) 아끼기
- 2026-11 에 타임라인의 1분 자동 갱신 때문에 DB가 잠들지 못해 무료 한도를 넘겼다. (지금은 수정됨)
- **주기적으로 DB에 닿는 요청을 만들지 않는다.** 화면의 자동 갱신(폴링), Vercel cron, DB를 조회하는 헬스체크 등.
  시계·색 갱신처럼 브라우저 안에서 할 수 있는 것은 서버를 부르지 않는다.
- 꼭 필요하면 간격이 5분보다 짧지 않은지, 아무도 안 볼 때 멈추는지 확인하고 먼저 사용자에게 설명한다.
- `/api/health` 는 DB를 쓰지 않는다. 계속 그렇게 둔다.

### 이 컴퓨터 — 다른 프로젝트에 영향 주지 않기
- 파일은 이 저장소 안에서만 만들고 고친다. 임시 파일은 Claude 스크래치 폴더에 둔다.
- 전역 설치를 하지 않는다(`pip install` 은 `backend/venv` 안에서만, `npm -g` 금지). `~/.bashrc`, git 전역 설정, 시스템 환경변수를 바꾸지 않는다.
- 포트는 **9081(백엔드), 5173(화면)** 만 쓰고, 쓰기 전에 비어 있는지 확인한다. **8000번대 포트는 쓰지 않는다.**
- 다른 프로그램의 프로세스나 사용자가 직접 띄운 서버를 종료하지 않는다. Claude 가 띄운 것은 작업이 끝나면 정리한다.
- `sudo` 가 필요한 명령은 직접 실행하지 않고 사용자에게 알려준다.
- 예전 systemd 서비스 `gpu-reserve` 는 꺼져 있다. 켜거나 지우는 것도 사용자에게 묻는다.

## 자주 쓰는 명령어

> **주의:** 이 컴퓨터는 ROS(`/opt/ros/jazzy`)가 `PYTHONPATH`에 들어 있어서 pytest가 ROS 플러그인을 잘못 읽는다.
> 그래서 파이썬 명령에는 `PYTHONPATH=` 를 붙여 ROS 경로를 그 명령에서만 잠깐 비운다.

| | 실서비스 | 로컬 개발 |
|---|---|---|
| 실행 | Vercel (서버리스) | 터미널에서 직접 |
| 주소 | Vercel 도메인 | 화면 5173 / 백엔드 9081 |
| 설정 | `backend/config.vercel.yaml` + Vercel 환경변수 | `backend/config.dev.yaml` |
| DB | Neon Postgres | `backend/dev/dev.db` (SQLite) |

### 처음 한 번만 (설치)
```bash
cd backend
python3 -m venv venv
PYTHONPATH= venv/bin/pip install -r requirements.txt
PYTHONPATH= venv/bin/python scripts/init_dev.py   # config.dev.yaml + 개발 DB 폴더

cd ../frontend
npm install
```

### 로컬 개발 — 터미널 2개
```bash
# 터미널 1 — 백엔드 (9081, 개발 DB)
cd backend
GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 9081
# API 직접 눌러보기: http://localhost:9081/docs

# 터미널 2 — 화면 (5173)
cd frontend
npm run dev        # http://localhost:5173
```

- 화면의 `/api/...` 요청은 vite 가 9081 로 넘겨준다 (`frontend/vite.config.js` 의 proxy).
- 개발용 가입 코드는 `DEV-CODE-1234` (`config.dev.yaml`).
- 개발 DB 비우기: `rm -f backend/dev/dev.db*` (Neon·`data/gpu.db` 와 다른 파일이라 안전)
- **`GPU_RESERVE_CONFIG=config.dev.yaml` 을 빠뜨리면 `config.yaml` → `data/gpu.db` 를 쓰게 된다. 항상 붙인다.**
- 빌드 확인이 필요하면 `frontend/dist` 대신 임시 폴더로 낸다:
  `npx vite build --outDir <스크래치 폴더>/build-check --emptyOutDir`
  (실서비스 빌드는 Vercel 이 직접 하므로 로컬 `dist` 는 필요 없다)

### 테스트
테스트는 매번 임시 폴더에 새 SQLite DB를 만들어 쓴다. `DATABASE_URL` 은 붙이지 않는다.
```bash
cd backend
PYTHONPATH= venv/bin/python -m pytest          # 전체
PYTHONPATH= venv/bin/python -m pytest -v       # 테스트 이름까지
PYTHONPATH= venv/bin/python -m pytest tests/test_overlap.py   # 파일 하나만
```

### 배포 (README 4장)
```bash
git checkout main && git pull
git checkout -b 작업-이름
# ... 수정, 테스트 ...
git add <파일> && git commit -m "무엇을 고쳤는지"
git push -u origin 작업-이름
# → Vercel Preview 자동 생성 → 사용자가 확인 → GitHub에서 PR → 사용자가 merge → 자동 배포
```
merge 후 로컬 정리: `git checkout main && git pull && git branch -d 작업-이름`
(이 컴퓨터에는 `gh` 가 없다. PR 은 사용자가 브라우저에서 만든다)

### Neon 대상 스크립트 (사용자가 직접 실행)
```bash
cd backend
DATABASE_URL='(Neon 접속 주소)' GPU_RESERVE_CONFIG=config.vercel.yaml \
GPU_RESERVE_INVITE_CODE='(가입 코드)' GPU_RESERVE_JWT_SECRET='(비밀키)' \
  PYTHONPATH= venv/bin/python scripts/<스크립트>
```
| 스크립트 | 하는 일 |
|---|---|
| `init_db.py` | 테이블·겹침 제약·GPU 목록 준비 (여러 번 실행해도 안전, 기존 데이터 유지) |
| `create_admin.py --email ...` | 첫 관리자. 이미 가입한 이메일이면 그 계정을 관리자로 올린다 |
| `set_admin.py 이메일 [--revoke]` / `--list` | 관리자 권한 주기·빼기·목록 (웹에서 막혔을 때 비상구) |
| `reset_password.py 이메일` | 비밀번호 재설정 |

평소 관리자 권한 변경은 웹의 관리자 → 가입자 탭에서 한다. 권한을 바꾸면 그 사람은 다시 로그인해야 메뉴가 바뀐다.

### 문제 확인
- API 살아 있는지: `(사이트 주소)/api/health` → `{"status":"ok"}`
- 서버 오류: Vercel → 해당 배포 → **Runtime Logs** / 빌드 오류: **Build Logs**
- DB 사용량: Neon → **Monitoring**(Compute 그래프), **Billing**
- 되돌리기: Vercel → Deployments → 잘 되던 배포 → `...` → **Promote to Production**
- 로그인이 꼬였을 때: 브라우저 F12 → Application → Local Storage → `gpu-reserve-token` 삭제
- 휴대폰 화면 크기 확인: PC 크롬 **F12 → Ctrl+Shift+M**

### 타임라인 데모 데이터 (로컬 전용)
Neon·개발 DB·`data/gpu.db` 를 건드리지 않고 `backend/demo/` 에 따로 만든다 (git 제외).
```bash
cd backend
PYTHONPATH= venv/bin/python scripts/seed_demo.py      # 데모 DB + 예약 16건
GPU_RESERVE_CONFIG=demo/config.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 9081
```
다른 터미널에서 `cd frontend && npm run dev` → http://localhost:5173
데모 로그인: `minjun@example.com` / `demo1234`. 지우기: `rm -rf backend/demo`

## 참고 파일

| 파일 | 역할 |
|---|---|
| `README.md` | 운영 안내 (사용자가 보는 문서) |
| `SPEC.md` / `PLAN.md` | 요구사항 / 전체 설계 |
| `vercel.json` | Vercel 빌드·라우팅 (`/api/*` → 함수, 나머지 → `index.html`) |
| `api/index.py` | Vercel 함수 진입점. backend 경로·`config.vercel.yaml` 지정, DB 자동 준비 끔, `DATABASE_URL` 필수 확인 |
| `.vercelignore` | Vercel 에 올리지 않을 파일 (venv, DB, 비밀 설정, tests, scripts, deploy) |
| `backend/config.vercel.yaml` | 배포용 설정 (git 포함, 비밀값 없음). GPU 목록은 여기서 고친다 |
| `backend/app/database.py` | `DATABASE_URL` 있으면 Postgres, 없으면 SQLite |
| `backend/app/models.py` | 테이블 + Postgres 겹침 금지 제약(EXCLUDE) |
| `backend/app/services/reservation_rules.py` | 예약 규칙 검사의 단일 창구 |
| `backend/tests/conftest.py` | 테스트용 임시 설정·DB, 시각 고정 |
| `backend/app/static_files.py`, `deploy/` | 예전 자체 서버 운영용. Vercel 에서는 쓰지 않는다 |
