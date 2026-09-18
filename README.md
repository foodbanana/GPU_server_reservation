# MORIN GPU 예약 시스템

연구실 GPU 서버 3대(GPU 12장)의 사용 시간을 예약하고, 예약 현황을 시간표로 확인하는 웹 서비스.

현재 **Vercel + Neon Postgres** 로 배포되어 운영 중이다. 브라우저만 있으면 어디서든 접속할 수 있고,
따로 켜 두어야 하는 서버 컴퓨터는 없다.

> 과거에는 연구실 리눅스 서버에서 systemd 로 직접 운영했다.
> 그때의 설치·백업·방화벽 절차가 필요하면 git 히스토리의 예전 README 를 참고한다.

---

## 목차

1. [무엇을 하는 서비스인가](#1-무엇을-하는-서비스인가)
2. [구조 (세 조각)](#2-구조-세-조각)
3. [환경변수](#3-환경변수)
4. [코드를 고치면 어떻게 배포되나](#4-코드를-고치면-어떻게-배포되나)
5. [DB 첫 준비 (새 Neon DB를 쓸 때)](#5-db-첫-준비-새-neon-db를-쓸-때)
6. [관리자 기능](#6-관리자-기능)
7. [로컬 개발](#7-로컬-개발)
8. [문제가 생기면](#8-문제가-생기면)
9. [폴더 구조](#9-폴더-구조)

---

## 1. 무엇을 하는 서비스인가

연구실 사람들이 GPU를 겹치지 않게 나눠 쓰도록 도와주는 예약 시스템이다.

**핵심 규칙**

| 규칙 | 내용 |
|---|---|
| 겹침 금지 | 같은 GPU에서 시간이 겹치는 예약은 **서버가 거부**한다. 두 사람이 같은 순간에 눌러도 한 명만 성공한다 |
| 시간 단위 | 1시간. 정시에 시작해서 정시에 끝난다 (예: 14:00 ~ 18:00) |
| 지난 시각 | 이미 지난 시각으로는 예약할 수 없다 (기준은 '현재 시각이 속한 정시') |
| 예약 길이 | **제한 없다.** 며칠짜리도 가능하며, 연구실 내 협의로 쓴다 |
| 시간대 | 모든 시간은 **한국 시간(Asia/Seoul)** 기준 |

겹침 판정은 `새 시작 < 기존 종료 AND 새 종료 > 기존 시작` 이다.
끝나는 시각과 시작 시각이 같은 경우(10시 종료 ↔ 10시 시작)는 겹치지 않는 것으로 본다.

**주요 화면**

- **타임라인** — 2주치 예약 현황을 시간표로 보여 준다. 이전/다음 2주로 옮겨 더 먼 미래도 볼 수 있다.
  GPU 12행을 단주기 6개 / 장주기 6개로 나눠 보여 주고, 현재 시각을 세로선으로 표시한다.
- **예약 신청** — GPU를 고르고 시작·종료 시각을 정한다.
- **내 예약** — 시작 전인 예약은 취소, 사용 중인 예약은 조기 종료(남은 시간 반납)할 수 있다.
- **관리자** — 전체 예약 관리와 가입자 관리. [6장](#6-관리자-기능) 참고.

자세한 요구사항은 `SPEC.md`, 설계는 `PLAN.md` 참고.

---

## 2. 구조 (세 조각)

서비스는 세 군데에 나뉘어 있다. 하나씩 무슨 일을 하는지 알면 문제가 생겼을 때 어디를 볼지 바로 안다.

```
     [사용자 브라우저]
            │
            ▼
   ┌──────────────────────────────────────┐
   │              Vercel                  │
   │                                      │
   │  ① 화면 (Vue 3 + Vite 빌드 결과)      │   ← 정적 파일을 그대로 내보낸다
   │  ② API  (FastAPI 서버리스 함수)       │   ← /api/... 요청만 여기로
   └──────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Neon Postgres        │   ← 계정·예약 데이터 저장 (미국 us-east)
        └────────────────────────┘

        [GitHub]  ── main 브랜치에 push 되면 Vercel이 자동 배포
```

| 조각 | 무엇 | 하는 일 |
|---|---|---|
| **GitHub** | 코드 보관 | `main` 브랜치가 **프로덕션**이다. 여기에 merge 되면 바로 배포된다 |
| **Vercel** | 실행 | 화면(정적 파일)을 내보내고, `/api/...` 요청은 FastAPI를 **서버리스 함수**로 깨워서 처리한다 |
| **Neon** | 데이터 | 계정·예약을 저장하는 Postgres. 미국 us-east 리전 |

**서버리스가 무슨 뜻인가**
항상 켜져 있는 서버가 없다는 뜻이다. 요청이 올 때만 함수가 깨어나 처리하고, 한동안 요청이 없으면
잠든다. 그래서 켜 두어야 할 컴퓨터도, 재시작해야 할 서비스도 없다.
대신 **한동안 아무도 안 쓰다가 처음 접속하면 1~2초 정도 느릴 수 있다.** 이는 정상이다.

**기술 스택**

| 영역 | 사용 기술 |
|---|---|
| 화면 | Vue 3, Vite, Vue Router, Pinia |
| 서버 | Python 3.12, FastAPI, SQLAlchemy 2, PyJWT, bcrypt |
| DB | Neon Postgres (로컬 개발에서는 SQLite) |
| 배포 | Vercel (`vercel.json`, 진입점은 루트 `api/index.py`) |

---

## 3. 환경변수

비밀값은 **코드나 설정 파일에 절대 적지 않는다.** 전부 Vercel 대시보드의 환경변수로 넣는다.

> 설정 위치: Vercel 프로젝트 → **Settings → Environment Variables**
> (Production / Preview / Development 을 모두 체크한다)

| 이름 | 필수 | 역할 |
|---|:---:|---|
| `DATABASE_URL` | 필수 | Neon Postgres 접속 주소. **이 값이 없으면 API가 뜨지 않는다.** 이 값이 있으면 Postgres, 없으면 SQLite로 동작한다 |
| `GPU_RESERVE_INVITE_CODE` | 필수 | 연구실 가입 코드. 회원가입할 때 이 코드를 맞게 입력해야 가입된다 |
| `GPU_RESERVE_JWT_SECRET` | 필수 | 로그인 토큰에 서명하는 비밀키. **바꾸면 모든 사용자가 로그아웃된다** |
| `GPU_RESERVE_SUPER_ADMIN_EMAIL` | 선택 | 최고 관리자로 보호할 이메일. 이 계정은 아무도(본인 포함) 관리자에서 해제할 수 없다. 넣지 않으면 이 보호만 꺼지고 나머지 기능은 정상 동작한다 |

**값은 이 문서에 적지 않는다.** 이 저장소는 공개되어 있다.
실제 값이 필요하면 Vercel 대시보드에서 확인한다.

**환경변수를 바꾼 뒤에는 재배포해야 적용된다.**
Vercel → Deployments → 최신 항목 → `...` → **Redeploy**

비밀이 아닌 설정(GPU 목록, 시간대, 타임라인 일수 등)은 git에 커밋되는
`backend/config.vercel.yaml` 에 들어 있다. GPU 모델명이나 번호를 바꾸려면 이 파일을 고친다.

---

## 4. 코드를 고치면 어떻게 배포되나

`main` 브랜치가 **프로덕션**이다. main에 들어간 코드는 곧바로 실서비스에 반영된다.
그래서 main에 직접 push하지 말고 아래 순서를 따른다.

```bash
# 1) 브랜치를 만든다
git checkout main
git pull
git checkout -b 작업-이름

# 2) 고치고 커밋
git add .
git commit -m "무엇을 고쳤는지"

# 3) 올린다
git push -u origin 작업-이름
```

```
push ──▶ Vercel이 Preview 배포를 자동 생성 (실서비스와 별개 주소)
                          │
                          ▼
             Preview 주소에서 직접 확인
                          │
                          ▼
        GitHub에서 Pull Request → main에 merge
                          │
                          ▼
              Vercel이 프로덕션 자동 재배포
```

**Preview 배포**는 실서비스와 다른 임시 주소로 뜬다. 여기서 먼저 눌러 보고 merge 하는 것이 안전하다.
Preview 주소는 GitHub PR 화면이나 Vercel 대시보드의 Deployments 목록에서 볼 수 있다.

> **주의: Preview 배포도 프로덕션과 같은 Neon DB를 쓴다.**
> Preview에서 만든 계정·예약은 실제 데이터에 그대로 반영된다. 시험 삼아 넣은 예약도
> 연구실 사람들 화면에 보인다는 뜻이다. 자세한 내용은 [8장](#8-문제가-생기면) 참고.

**merge 전에 로컬에서 테스트를 돌려 보는 것을 권장한다.**

```bash
cd backend
PYTHONPATH= venv/bin/python -m pytest
```

---

## 5. DB 첫 준비 (새 Neon DB를 쓸 때)

Neon 프로젝트를 새로 만들었거나 DB를 비우고 다시 시작할 때만 하는 작업이다.
**평소 운영에서는 할 일이 없다.**

서버리스에서는 요청이 올 때마다 테이블을 확인하면 느려지므로, 자동 준비를 꺼 두었다.
대신 아래 명령을 **로컬에서 한 번** 실행한다. (비밀값은 명령 앞에 붙여서 그때만 넘긴다)

### 5-1. 테이블 · GPU · 겹침 방지 제약 만들기

```bash
cd backend

DATABASE_URL='(Neon 접속 주소)' \
GPU_RESERVE_CONFIG=config.vercel.yaml \
GPU_RESERVE_INVITE_CODE='(가입 코드)' \
GPU_RESERVE_JWT_SECRET='(비밀키)' \
  PYTHONPATH= venv/bin/python scripts/init_db.py
```

하는 일 세 가지다.

1. 테이블(`users`, `gpus`, `reservations`)을 만든다
2. Postgres에 **겹침 방지 제약**을 건다 — 같은 GPU에 시간이 겹치는 예약이 DB 차원에서 거부된다
3. `config.vercel.yaml` 의 목록대로 GPU 12장을 등록한다

**여러 번 실행해도 안전하다.** 이미 있는 것은 건드리지 않고, **기존 예약이나 계정을 지우지 않는다.**
GPU 목록(모델명·번호)을 바꿨을 때 다시 실행하면 GPU 정보만 갱신된다.

### 5-2. 첫 관리자 계정 만들기

웹 회원가입만으로는 관리자가 될 수 없다. 첫 관리자는 이 명령으로 만든다.

```bash
cd backend

DATABASE_URL='(Neon 접속 주소)' \
GPU_RESERVE_CONFIG=config.vercel.yaml \
GPU_RESERVE_INVITE_CODE='(가입 코드)' \
GPU_RESERVE_JWT_SECRET='(비밀키)' \
  PYTHONPATH= venv/bin/python scripts/create_admin.py --email someone@example.com
```

- **이미 웹으로 가입한 이메일이면 계정을 새로 만들지 않고 그 계정을 관리자로 올린다.**
  (이름·비밀번호는 그대로 둔다) — 이 방법을 권장한다.
- 가입한 적 없는 이메일이면 이름과 비밀번호를 물어보고 새로 만든다.

**첫 관리자를 만든 뒤에는 터미널을 쓸 일이 거의 없다.**
그다음부터는 관리자가 웹 화면에서 다른 사람을 관리자로 올릴 수 있다.

---

## 6. 관리자 기능

관리자로 로그인하면 상단에 **관리자** 메뉴가 생긴다. 탭이 두 개다.

### 전체 예약 탭

- 모든 사람의 예약을 본다 (상태·기간으로 걸러 볼 수 있다)
- 예약의 **시작·종료 시각을 수정**한다 (GPU와 예약자는 바꿀 수 없다)
- 예약을 **강제 취소**한다 (기록은 남고 상태만 '취소됨'으로 바뀐다)

관리자도 겹침 규칙을 똑같이 적용받는다. 다른 예약과 겹치면 저장되지 않는다.
다만 **이미 시작된 예약은 시작 시각을 그대로 두고 종료 시각만** 바꾸면 연장·단축할 수 있다.

### 가입자 탭

- 가입한 사람 목록을 본다 (이름, 이메일, 권한, 가입일, 현재·예정 예약 수)
- **관리자로 승격 / 관리자 해제** 버튼으로 권한을 바꾼다

권한 변경에는 안전장치가 세 개 있다. 모두 **서버가** 막는다(화면에서도 버튼이 비활성화된다).

| 막는 경우 | 이유 |
|---|---|
| 최고 관리자 해제 | `GPU_RESERVE_SUPER_ADMIN_EMAIL` 로 지정한 계정은 **본인 포함 누구도** 해제할 수 없다 |
| 자기 자신 해제 | 누르는 순간 관리자 화면에서 튕겨 나가 혼란스럽다. 다른 관리자에게 부탁한다 |
| 마지막 관리자 해제 | 관리자가 0명이 되면 아무도 관리자 화면에 못 들어간다 |

권한을 바꾸면 **그 사람은 로그아웃했다가 다시 로그인해야** 메뉴가 바뀐다.

### 비밀번호

비밀번호는 **해시(bcrypt)로만 저장되어 원래 값을 볼 수 없다.** 관리자도 마찬가지다.
잊어버린 사람이 있으면 새 비밀번호로 재설정해 준다.

```bash
cd backend
DATABASE_URL='(Neon 접속 주소)' GPU_RESERVE_CONFIG=config.vercel.yaml \
GPU_RESERVE_INVITE_CODE='(가입 코드)' GPU_RESERVE_JWT_SECRET='(비밀키)' \
  PYTHONPATH= venv/bin/python scripts/reset_password.py someone@example.com
```

터미널에서 권한을 다루는 명령도 그대로 남아 있다. 환경변수를 잘못 넣어 웹에서 손댈 수 없게 됐을 때
빠져나오는 비상구 역할을 한다.

```bash
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com           # 권한 주기
PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com --revoke  # 권한 빼기
PYTHONPATH= venv/bin/python scripts/set_admin.py --list                        # 관리자 목록
```

---

## 7. 로컬 개발

**환경변수 `DATABASE_URL` 을 넣지 않으면 SQLite 파일로 동작한다.** Neon에 붙지 않으므로
진짜 데이터를 건드릴 걱정 없이 마음껏 시험할 수 있다.

### 최초 1회

```bash
# 백엔드
cd backend
python3 -m venv venv
PYTHONPATH= venv/bin/pip install -r requirements.txt
PYTHONPATH= venv/bin/python scripts/init_dev.py     # config.dev.yaml + 개발용 DB 폴더 생성

# 화면
cd ../frontend
npm install
```

`init_dev.py` 가 만드는 개발용 설정의 가입 코드는 `DEV-CODE-1234` 다(`config.dev.yaml` 에 적혀 있다).

### 실행 — 터미널 두 개

**터미널 1 — 백엔드 (포트 9081)**
```bash
cd backend
GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 9081
```

**터미널 2 — 화면 (포트 5173)**
```bash
cd frontend
npm run dev
```

브라우저에서 **http://localhost:5173** 을 연다.
화면의 `/api/...` 요청은 Vite가 9081로 넘겨준다(`frontend/vite.config.js` 의 proxy 설정).
API를 직접 눌러 보려면 http://localhost:9081/docs 로 간다.

| | 값 |
|---|---|
| 화면 | http://localhost:5173 |
| 백엔드 | http://localhost:9081 |
| 설정 파일 | `backend/config.dev.yaml` |
| DB | `backend/dev/dev.db` (SQLite) |
| 개발 DB 비우기 | `rm -f backend/dev/dev.db*` |

### 테스트

```bash
cd backend
PYTHONPATH= venv/bin/python -m pytest        # 전체
PYTHONPATH= venv/bin/python -m pytest -v     # 테스트 이름까지
```

테스트는 매번 **임시 폴더에 새 DB를 만들어** 쓴다. 개발 DB나 Neon을 건드리지 않는다.

`DATABASE_URL` 을 앞에 붙이면 Postgres로도 같은 테스트를 돌릴 수 있다.
다만 **테스트가 그 DB의 테이블을 모두 지웠다 다시 만들므로, 반드시 테스트 전용 DB 주소만 넣는다.**

> **참고:** 이 명령들에 붙은 `PYTHONPATH=` 는 개발 컴퓨터에 설치된 ROS 경로를 잠깐 비워
> pytest가 엉뚱한 플러그인을 읽지 않게 하는 것이다. ROS가 없는 컴퓨터라면 없어도 된다.

---

## 8. 문제가 생기면

**증상으로 어디를 볼지 먼저 나눈다.**

| 증상 | 원인일 가능성이 높은 곳 | 볼 곳 |
|---|---|---|
| 화면이 아예 안 뜬다 / 404 | Vercel 빌드 또는 배포 | Vercel → Deployments → 해당 배포의 **Build Logs** |
| 화면은 뜨는데 로그인·예약이 안 된다 | Neon 또는 `DATABASE_URL` | Vercel → **Runtime Logs**, Neon 대시보드 |
| 로그인이 자꾸 풀린다 | `GPU_RESERVE_JWT_SECRET` 이 바뀌었다 | Vercel 환경변수 |
| 회원가입이 안 된다 | 가입 코드 불일치 | `GPU_RESERVE_INVITE_CODE` 값과 사람들에게 알려 준 코드 비교 |
| 첫 접속만 1~2초 느리다 | **정상이다** | 아래 설명 참고 |

### 주의: Preview 배포도 프로덕션 DB를 쓴다

**Preview 배포도 프로덕션과 같은 Neon DB를 사용하므로, Preview에서 만든 데이터는
실제 데이터에 그대로 반영된다.** Preview는 화면과 코드만 따로 뜨는 것이지 데이터가 분리되는 것이 아니다.

| Preview에서 한 일 | 결과 |
|---|---|
| 시험용 계정으로 가입 | 실제 가입자 목록에 그대로 남는다 |
| 시험 삼아 예약 생성 | 연구실 사람들 타임라인에 보이고, 그 시간을 남이 못 쓴다 |
| 예약 취소·삭제 | 진짜로 취소된다 |
| 관리자 권한 변경 | 실제 권한이 바뀐다 |

그래서 Preview에서 시험한 뒤에는 **만들어 둔 시험 데이터를 반드시 정리한다.**
화면 모양만 확인할 때는 문제없지만, 데이터를 만들거나 지우는 기능을 시험할 때는 주의한다.
마음 편히 시험하려면 로컬 개발([7장](#7-로컬-개발))을 쓴다. 로컬은 SQLite라 Neon에 닿지 않는다.

### Neon이 잠드는 것에 대해

무료 플랜의 Neon은 **약 5분 동안 접속이 없으면 잠든다.** 그 뒤 첫 요청이 오면 깨어나는 데
1~2초 정도 걸린다. 이건 고장이 아니라 원래 그런 동작이다. 잠깐 기다리면 그다음부터는 빠르다.
연구실 사람들에게 "처음 한 번 느린 건 정상"이라고 알려 두면 문의가 줄어든다.

### 자주 쓰는 확인 방법

| 하고 싶은 것 | 방법 |
|---|---|
| API가 살아 있는지 | 브라우저에서 `(사이트 주소)/api/health` → `{"status":"ok"}` 가 나오면 정상 |
| 서버 오류 메시지 보기 | Vercel → 해당 배포 → **Runtime Logs** |
| 내 로그인 상태 초기화 | 브라우저 F12 → Application → Local Storage → `gpu-reserve-token` 삭제 |
| 배포를 되돌리기 | Vercel → Deployments → 잘 되던 배포 → `...` → **Promote to Production** |

**문제가 커지면 되돌리는 것이 먼저다.** 원인 파악은 그다음에 해도 된다.
Vercel은 예전 배포를 그대로 보관하므로 위 방법으로 몇 초 만에 되돌릴 수 있다.

### 데이터 백업

Neon이 자체적으로 백업(복구 지점)을 관리한다. Neon 대시보드에서 확인할 수 있다.
따로 서버에서 돌리는 백업 스크립트는 더 이상 쓰지 않는다.

---

## 9. 폴더 구조

```
GPU_server_reservation_ws/
├── README.md                이 문서
├── SPEC.md                  요구사항
├── PLAN.md                  설계
├── vercel.json              Vercel 배포 설정 (빌드·라우팅)
├── requirements.txt         Vercel 함수용 파이썬 라이브러리 목록
├── .python-version          Vercel에서 쓸 파이썬 버전 (3.12)
│
├── api/
│   └── index.py             Vercel 서버리스 함수 진입점 (backend/app 을 불러온다)
│
├── backend/
│   ├── app/                 서버 코드 (FastAPI)
│   │   ├── main.py          앱 조립
│   │   ├── models.py        DB 테이블 + 겹침 방지 제약
│   │   ├── database.py      DATABASE_URL 있으면 Postgres, 없으면 SQLite
│   │   ├── db_init.py       테이블·제약·GPU 준비 (서버리스에서는 자동 실행 꺼짐)
│   │   ├── routers/         API 경로별 코드
│   │   └── services/        예약 규칙·계정 규칙 (판단 로직)
│   ├── scripts/             init_db, create_admin, set_admin, reset_password 등
│   ├── tests/               테스트 (pytest)
│   ├── config.vercel.yaml   배포용 설정 (git 포함, 비밀값 없음)
│   ├── config.example.yaml  설정 예시
│   ├── config.dev.yaml      로컬 개발 설정 (git 제외, init_dev.py 가 생성)
│   ├── dev/                 로컬 개발 DB (git 제외)
│   └── venv/                파이썬 가상환경 (git 제외)
│
├── frontend/
│   ├── src/                 화면 코드 (Vue 3)
│   │   ├── views/           화면별 컴포넌트 (타임라인, 예약, 내 예약, 관리자)
│   │   ├── api/client.js    서버 호출
│   │   └── router/          주소 연결 + 관리자 화면 차단
│   ├── vite.config.js       개발 서버 포트·proxy
│   └── dist/                빌드 결과 (git 제외, Vercel이 만든다)
│
└── deploy/                  과거 자체 서버 운영용 파일 (현재 사용하지 않음)
```

**git에 올라가지 않는 것:** `backend/config.yaml`, `backend/config.dev.yaml`, `backend/secrets/`,
`backend/venv/`, `backend/dev/`, `backend/demo/`, `data/*.db`, `node_modules/`, `frontend/dist/`

비밀값은 파일이 아니라 **Vercel 환경변수**에 있다. 이 저장소만 받아서는 서비스에 접속할 수 없다.
