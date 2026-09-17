# GPU 예약 시스템 — 전체 구현 계획

## Context (왜 이 작업을 하는가)

연구실 GPU 서버 3대(GPU 12장)를 여러 사람이 서로 겹치지 않게 나눠 쓰기 위한 웹 서비스를 만든다.
지금은 저장소에 `SPEC.md`와 `CLAUDE.md` 문서 2개만 있고 코드는 전혀 없는 상태다(빈 프로젝트).

목표는 SPEC.md 11장의 Phase 1~6을 순서대로 구현해서,
연구실 데스크탑(Ubuntu 24.04, 학교 내부망)에서 `http://<데스크탑 IP>:9080` 하나로
(8000번대는 강화학습·VLA 추론 서버와 충돌할 수 있어 피한다. 개발용 백엔드는 9081)
PC·휴대폰 모두 접속 가능한 예약 시스템을 돌리는 것이다.

이 문서는 **전체 설계도**다. 실제 코드는 Phase 단위로 따로 요청받아 작성한다.

---

## 확정된 결정사항 (SPEC에 없어서 이번에 정한 것)

| 항목 | 결정 |
|---|---|
| 로그인 유지 방식 | **JWT 토큰**, 유효기간 **30일** |
| 사용자당 예약 개수 제한 | **제한 없음** (설정값도 만들지 않음) |
| 타임라인 표시 | **14일 전체를 한 번에 그리고 가로 스크롤**, GPU 이름 열은 왼쪽 고정.<br>**이전/다음 버튼으로 14일씩 기간을 옮겨** 더 먼 미래도 본다 |
| 예약 길이·기간 제한 | **없음**. 단주기 최대·장주기 최소·최대 길이·14일 이내 시작 제한을 모두 없앴다(협의해서 사용).<br>단주기/장주기 **구분 자체는 유지**(버튼·타임라인 그룹·표시용) |
| 관리자 예약 수정 범위 | **시작·종료 시각만 수정** + 삭제. GPU·예약자 변경 불가.<br>**규칙은 일반 사용자와 동일**(겹침·정시·순서·지난 시각). 관리자만 무시할 수 있는 규칙은 없다 |
| 관리자 가입자 목록 | **보기 전용.** 이름·이메일·관리자 여부·가입일·현재/예정 예약 수.<br>계정 수정·삭제 기능은 만들지 않는다. 비밀번호 해시는 응답에 넣지 않는다 |
| 예약 시작 가능 시각 | **현재 시각이 속한 정시(내림)부터** 가능. 예: 14:20이면 14:00 시작 OK, 13:00은 거부 |
| 시간 저장 방식 | SPEC 2장대로 **DB에 KST(한국시간) 기준으로 저장**. API는 `+09:00`이 붙은 ISO8601 문자열로 주고받음 |

> **JWT**: 로그인하면 서버가 "출입증" 역할을 하는 긴 문자열을 발급하고, 브라우저가 그걸 보관했다가 요청마다 같이 보내는 방식.

---

## 1. 폴더 구조

```
GPU_server_reservation_ws/
├── SPEC.md
├── CLAUDE.md
├── README.md                    # Phase 5에서 작성 (설치·실행·백업 안내)
├── .gitignore                   # config.yaml, *.db, venv, node_modules, credentials/token
│
├── backend/
│   ├── requirements.txt
│   ├── config.example.yaml      # git에 커밋하는 예시 (비밀값은 비워둠)
│   ├── config.yaml              # 실제 설정 — git 커밋 금지
│   ├── app/
│   │   ├── main.py              # FastAPI 앱 생성, 라우터 등록, 정적파일 서빙(Phase 5)
│   │   ├── config.py            # config.yaml 읽어서 파이썬 객체로
│   │   ├── database.py          # SQLite 연결 (SQLAlchemy), WAL 모드 설정
│   │   ├── models.py            # DB 테이블 정의
│   │   ├── schemas.py           # 요청/응답 데이터 형식 (Pydantic)
│   │   ├── security.py          # 비밀번호 해시(bcrypt), JWT 발급·검증
│   │   ├── deps.py              # "현재 로그인 사용자", "관리자만" 검사
│   │   ├── timeutil.py          # KST 시간 처리, 정시 올림/내림
│   │   ├── seed.py              # config.yaml 기준으로 GPU 12장 DB 등록
│   │   ├── routers/
│   │   │   ├── auth.py          # 회원가입·로그인
│   │   │   ├── gpus.py          # GPU 목록
│   │   │   ├── reservations.py  # 예약 생성·조회·취소·조기종료
│   │   │   └── admin.py         # 관리자 전용
│   │   └── services/
│   │       ├── reservation_rules.py   # 규칙 검사 + 중복 검사 (핵심 로직)
│   │       └── google_calendar.py     # Phase 6
│   ├── scripts/
│   │   ├── create_admin.py      # 첫 관리자 계정 생성 (명령줄)
│   │   └── reset_password.py    # 사용자 비밀번호 재설정 (명령줄)
│   └── tests/
│       ├── conftest.py          # 테스트용 임시 DB 준비
│       ├── test_auth.py
│       ├── test_rules.py
│       ├── test_overlap.py
│       └── test_permissions.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js           # 개발 중 /api 요청을 9081 포트로 넘겨주는 proxy 설정
│   ├── index.html
│   └── src/
│       ├── main.js, App.vue
│       ├── router/index.js      # 화면 주소 연결, 로그인 안 했으면 로그인 화면으로
│       ├── api/client.js        # 서버 호출 공통 함수 (JWT 자동 첨부, 에러 메시지 처리)
│       ├── stores/auth.js       # 로그인 상태 보관 (Pinia)
│       ├── views/
│       │   ├── LoginView.vue
│       │   ├── SignupView.vue
│       │   ├── TimelineView.vue        # 메인 예약 현황
│       │   ├── NewReservationView.vue  # 예약 신청
│       │   ├── MyReservationsView.vue  # 내 예약
│       │   └── AdminView.vue           # 관리자
│       └── components/
│           ├── GpuButtonGrid.vue       # 단주기 6 / 장주기 6 버튼
│           ├── TimelineGrid.vue        # 12행 × 336칸 표
│           └── ReservationTooltip.vue
│
├── deploy/
│   ├── gpu-reserve.service      # systemd 파일
│   └── backup_db.sh             # 매일 DB 백업 스크립트
│
└── data/                        # git 커밋 금지
    └── gpu.db
```

---

## 2. 설정 파일 (`backend/config.yaml`)

코드에 값을 박지 않기 위한 파일. 구조:

```yaml
app:
  timezone: "Asia/Seoul"
  invite_code: "여기에-연구실-가입코드"
  jwt_secret: "여기에-긴-임의-문자열"
  jwt_expire_days: 30

rules:
  slot_minutes: 60            # 예약 단위 (1시간)
  timeline_days: 14           # 타임라인이 한 번에 보여 주는 일수 (화면 표시용, 예약 제한 아님)

gpus:                         # 서버3 A100/maxQ 번호가 반대면 여기만 고치면 됨
  - { server_no: 1, gpu_index: 0, model: "A6000",     category: short }
  - { server_no: 1, gpu_index: 1, model: "A6000",     category: short }
  - { server_no: 1, gpu_index: 2, model: "A6000",     category: long  }
  - { server_no: 1, gpu_index: 3, model: "A6000",     category: long  }
  - { server_no: 2, gpu_index: 0, model: "RTX 3090",  category: short }
  - { server_no: 2, gpu_index: 1, model: "RTX 3090",  category: short }
  - { server_no: 2, gpu_index: 2, model: "RTX 3090",  category: long  }
  - { server_no: 2, gpu_index: 3, model: "RTX 3090",  category: long  }
  - { server_no: 3, gpu_index: 0, model: "A100",      category: short }
  - { server_no: 3, gpu_index: 1, model: "A100",      category: long  }
  - { server_no: 3, gpu_index: 2, model: "maxQ 6000", category: short }
  - { server_no: 3, gpu_index: 3, model: "maxQ 6000", category: long  }

google:                       # Phase 6
  enabled: false
  calendar_id: "primary"
  credentials_path: "secrets/credentials.json"
  token_path: "secrets/token.json"
```

`config.example.yaml`은 비밀값(`invite_code`, `jwt_secret`)을 비운 사본으로 git에 커밋한다.

---

## 3. DB 테이블 설계 (SQLite)

### `users`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT NOT NULL | 예약 블록에 표시될 이름 |
| email | TEXT NOT NULL UNIQUE | 로그인 ID 겸 구글 캘린더 초대 주소 |
| password_hash | TEXT NOT NULL | bcrypt 해시. 평문 저장 금지 |
| is_admin | BOOLEAN NOT NULL DEFAULT 0 | |
| created_at | DATETIME NOT NULL | |

### `gpus`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| server_no | INTEGER NOT NULL | 1, 2, 3 |
| gpu_index | INTEGER NOT NULL | 0~3 |
| model | TEXT NOT NULL | "A6000" 등. config에서 바꾸면 갱신 |
| category | TEXT NOT NULL | `short`(단주기) / `long`(장주기) |
| sort_order | INTEGER NOT NULL | 타임라인 행 순서 |

- `UNIQUE(server_no, gpu_index)`
- 앱 시작 시 `seed.py`가 config.yaml과 대조해서 없으면 추가, `model`/`category`가 바뀌었으면 갱신.

### `reservations`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| gpu_id | INTEGER NOT NULL FK→gpus.id | |
| user_id | INTEGER NOT NULL FK→users.id | |
| start_at | DATETIME NOT NULL | KST 기준, 항상 정시(분·초 0) |
| end_at | DATETIME NOT NULL | KST 기준, 항상 정시 |
| status | TEXT NOT NULL | `active` / `cancelled` |
| created_at | DATETIME NOT NULL | |
| updated_at | DATETIME NOT NULL | |
| google_event_id | TEXT NULL | Phase 6 |

- 인덱스: `(gpu_id, start_at, end_at)`, `(user_id)`, `(status)`
- **취소는 행을 지우지 않고 `status='cancelled'`로 바꾼다** (기록 보존 + 구글 일정 삭제 재시도에 필요).
  중복 검사는 `status='active'`인 것만 본다.
- "예약 가능 / 예약됨 / 사용 중"은 **저장하지 않고** 현재 시각과 비교해 계산한다(SPEC 7장).
- 조기 종료 = `end_at`을 현재 시각 정시 올림으로 줄이는 것. 별도 상태 없음.

### `google_sync_tasks` (Phase 6에서 추가)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| reservation_id | INTEGER NOT NULL | |
| action | TEXT NOT NULL | `create` / `update` / `delete` |
| attempts | INTEGER DEFAULT 0 | |
| last_error | TEXT NULL | |
| done | BOOLEAN DEFAULT 0 | |
| created_at | DATETIME NOT NULL | |

구글 API 호출이 실패해도 예약은 유지하고, 여기에 남겨서 나중에 재시도한다(SPEC 9장).

### 동시 예약 대비 (중복 저장 방지)
SQLite에는 "시간 겹침 금지" 제약을 직접 걸 수 없으므로:
1. DB를 **WAL 모드**로 켠다 (읽기와 쓰기가 서로 덜 막힘).
2. 예약 생성·수정은 `BEGIN IMMEDIATE` 트랜잭션 안에서 **겹침 재확인 → INSERT**를 한 묶음으로 처리한다.
   → 두 사람이 같은 순간에 눌러도 한 명만 성공한다 (SPEC 5장).

---

## 4. API 목록

모든 경로는 `/api` 아래. 실패 응답은 `{"detail": "한국어 메시지"}` 형태로 통일한다.

### 인증
| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| POST | `/api/auth/signup` | 이름·이메일·비밀번호·가입코드로 가입. 코드 틀리면 400 | 누구나 |
| POST | `/api/auth/login` | 이메일·비밀번호 → JWT 토큰(30일) 발급 | 누구나 |
| GET | `/api/auth/me` | 현재 로그인한 사용자 정보 | 로그인 |

### 조회
| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| GET | `/api/config` | 프론트가 쓸 규칙값(시간 단위, 최소/최대 시간, 예약 가능 범위) | 누구나 |
| GET | `/api/gpus` | GPU 12장 목록 (서버번호·번호·모델·분류·정렬순서) | 로그인 |
| GET | `/api/reservations?start=&end=` | 기간 내 전체 예약 (타임라인용, 예약자 이름 포함) | 로그인 |
| GET | `/api/reservations/me` | 내 예약 목록 | 로그인 |
| GET | `/api/gpus/{gpu_id}/reservations?start=&end=` | 특정 GPU의 예약된 시간대 (예약 신청 화면용) | 로그인 |

### 예약 변경
| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| POST | `/api/reservations` | 예약 생성 `{gpu_id, start_at, end_at}`. 규칙 위반 400 / 중복 409 | 로그인 |
| DELETE | `/api/reservations/{id}` | 취소 (시작 전인 것만) | 본인 또는 관리자 |
| POST | `/api/reservations/{id}/end-now` | 조기 종료 (사용 중인 것만) | 본인 또는 관리자 |

### 관리자
| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| GET | `/api/admin/reservations` | 전체 예약 목록 (지난 것 포함, 필터·페이지) | 관리자 |
| PATCH | `/api/admin/reservations/{id}` | **시작·종료 시각만** 수정. 규칙은 일반 예약과 동일.<br>시작을 그대로 두면 **사용 중인 예약도 종료 연장·단축 가능** | 관리자 |
| DELETE | `/api/admin/reservations/{id}` | 상태 무관 강제 삭제(취소 처리) | 관리자 |
| GET | `/api/admin/users` | 가입자 목록(보기 전용). 비밀번호 해시는 응답에 없음 | 관리자 |

### 정적 파일 (Phase 5)
| GET | `/` 및 나머지 경로 | Vue 빌드 결과(`frontend/dist`) 서빙. 새로고침 대비 `index.html` 폴백 |

---

## 5. 예약 규칙 검사 (백엔드 단일 창구)

`services/reservation_rules.py` 함수 하나에서 순서대로 검사하고, 첫 실패 시 한국어 메시지를 던진다.
생성·관리자 수정 **모두 이 함수를 거친다** (로직 중복 방지).
예약 길이·기간 제한을 없앤 뒤로는 관리자와 일반 사용자에게 같은 규칙이 적용되므로,
`as_admin` 인자도 '관리자만 무시' 개념도 더 이상 없다.

| # | 검사 | 관리자도 적용? |
|---|---|---|
| 1 | `start_at`, `end_at`이 정시인가 (분·초 0) | ✅ 항상 |
| 2 | `end_at > start_at` 인가 | ✅ 항상 |
| 3 | `start_at`이 **현재 시각이 속한 정시(내림) 이상**인가 | ✅ 항상 (예외 1개, 아래) |
| 4 | 같은 GPU의 다른 `active` 예약과 겹치는가 | ✅ **항상** (관리자도 절대 예외 없음) |

**검사 3의 예외 — 사용 중인 예약 연장.**
기존 예약을 수정할 때 새 `start_at`이 그 예약의 지금 `start_at`과 **같으면**(= 시작을 건드리지 않으면)
검사 3을 건너뛴다. 대신 '새 `end_at`이 지난 시각이면 안 된다'를 검사한다.
이게 없으면 지금 돌고 있는 예약(시작이 이미 과거)을 관리자가 연장해 줄 수 없다.
구현: `validate_reservation(..., current_start_at=reservation.start_at)`

> 예전에 있던 '14일 이내 시작'과 '분류별 최소~최대 길이' 검사는 없앴다.
> 사람들끼리 협의해서 쓰기로 했기 때문이다. 단주기/장주기 구분은 화면 표시용으로 남아 있다.

- **검사 3 (변경점)**: 현재가 14:20이면 `start_at`이 14:00인 예약은 **허용**한다(지금 당장 쓰기 시작하는 경우).
  13:00 시작은 거부. 즉 기준선은 "현재 시각 정시 **내림**"이다.
  → 조기 종료의 "현재 시각 정시 **올림**"과 기준이 다르다는 점에 주의(조기 종료는 SPEC 7장대로 올림 유지).
- **검사 6**: `새 시작 < 기존 종료 AND 새 종료 > 기존 시작`.
  경계가 맞닿는 경우(10시 종료 ↔ 10시 시작)는 허용. 수정 시에는 **자기 자신은 비교 대상에서 제외**한다.
- 관리자가 4·5를 무시하고 저장하면 응답에 "규칙을 무시하고 저장했습니다" 경고를 같이 담아 화면에 표시한다.

프론트엔드도 같은 검사를 하지만 **어디까지나 사용자 편의용**이고, 진짜 판정은 서버가 한다.

---

## 6. Phase별 작업 목록

> **각 Phase는 "환경 확인"부터 시작한다.**
> 필요한 프로그램이 설치되어 있는지 **먼저 확인 명령을 돌려보고**, 없으면 그 Phase 작업을 시작하기 전에
> **사용자가 직접 실행할 설치 명령을 안내한다.** (`sudo`가 필요한 명령은 절대 대신 실행하지 않는다 — CLAUDE.md 규칙)
> 설치가 끝났다는 확인을 받은 뒤에 코드 작성을 시작한다.

### Phase 1 — 백엔드 기초

**0) 환경 확인 (작업 시작 전)**

| 확인 명령 | 필요한 것 |
|---|---|
| `python3 --version` | Python 3.10 이상 |
| `python3 -m venv --help` | `python3-venv` 패키지 |
| `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` | SQLite (보통 기본 포함) |
| `git --version` | git |

없을 때 안내할 명령 (사용자가 직접 실행):
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

**1) 작업 목록**
- [ ] `.gitignore`, `backend/requirements.txt`, venv 안내
- [ ] `config.py` + `config.yaml` / `config.example.yaml`
- [ ] `database.py`(WAL 모드), `models.py` 3개 테이블, 앱 시작 시 테이블 생성
- [ ] `seed.py` — config 기준 GPU 12장 등록/갱신
- [ ] `security.py` — bcrypt 해시, JWT 발급·검증(30일) / `deps.py` — 로그인 사용자, 관리자 검사
- [ ] `timeutil.py` — KST now, 정시 올림/내림
- [ ] `routers/auth.py` — signup(가입코드 검사) / login / me
- [ ] `routers/gpus.py` — GPU 목록, `/api/config`
- [ ] `services/reservation_rules.py` — 위 4단계 검사
- [ ] `routers/reservations.py` — 생성(트랜잭션) / 조회 / 내 예약 / 취소 / 조기 종료
- [ ] pytest: 겹침 거부, 경계 맞닿음 허용, 길이·기간 제한이 없음, 가입코드 오류,
      **현재가 14:20일 때 14:00 시작은 허용 / 13:00 시작은 거부** (시간을 고정해서 테스트)

**완료 확인:** `pytest` 전부 통과 + `uvicorn` 실행 후 `http://localhost:9081/docs`에서 직접 호출해보기

### Phase 2 — 프론트엔드 기초

**0) 환경 확인 (작업 시작 전)**

| 확인 명령 | 필요한 것 |
|---|---|
| `node --version` | Node.js **24 LTS** (설치 완료: v24.21.0) |
| `npm --version` | npm (설치 완료: 11.19.0) |

없거나 버전이 낮을 때 안내할 명령 (사용자가 직접 실행):
```bash
# Ubuntu 24.04 기본 저장소 Node는 버전이 낮을 수 있으므로 NodeSource 사용
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
```

**1) 작업 목록**
- [ ] Vue 3 + Vite 프로젝트, Pinia, vue-router, vite proxy 설정
- [ ] `api/client.js` — JWT 자동 첨부, 401이면 로그인 화면으로, 서버 한국어 에러 그대로 표시
- [ ] `LoginView` / `SignupView`
- [ ] `GpuButtonGrid` — 단주기 6개 / 장주기 6개 버튼을 구분해 배치
- [ ] `NewReservationView` — 날짜·시간(정시) 선택, 해당 GPU의 기존 예약 시간대 함께 표시, 신청
- [ ] 규칙 위반·중복 시 에러 메시지 화면 표시

**완료 확인:** 브라우저에서 가입 → 로그인 → 예약 → 같은 시간 또 예약 시 한국어 오류 확인

### Phase 3 — 예약 현황 타임라인

**0) 환경 확인:** Phase 2와 동일 (추가 설치 없음). 휴대폰 확인을 위해 데스크탑과 휴대폰이 같은 네트워크인지,
`ip addr`로 데스크탑 IP를 확인해둔다.

**1) 작업 목록**
- [ ] `TimelineView` + `TimelineGrid` — 가로: 기준날짜 0시~14일 후 시간 칸 336개 / 세로: GPU 12행
- [ ] 이전 2주 / 오늘로 / 다음 2주 버튼 — 기준날짜를 옮겨 더 먼 미래도 본다
- [ ] 단주기 6행 / 장주기 6행 그룹 구분, 행 레이블에 서버·GPU 번호·모델명
- [ ] 색상: 예약 가능=초록, 예약됨=빨강, 사용 중=노랑, 지난 시간=회색
- [ ] 예약 블록에 예약자 이름, hover(PC)·tap(모바일) 시 예약자·시작·종료 표시
- [ ] 현재 시각 세로선, 첫 로드 시 현재 시각 위치로 자동 스크롤
- [ ] GPU 이름 열 왼쪽 고정 + 시간 축만 가로 스크롤, 페이지 전체는 가로로 넘치지 않게

**완료 확인:** 예약이 올바른 행·칸·색으로 보이는지, 휴대폰 브라우저에서 확인

### Phase 4 — 예약 관리와 관리자

**0) 환경 확인:** 추가 설치 없음 (Phase 1·2 환경 그대로).

**1) 작업 목록**
- [ ] `MyReservationsView` — 내 예약 목록, 취소 / 조기 종료 버튼 (상태에 따라 활성화)
- [ ] `AdminView` — 탭 2개: (1) 전체 예약 목록·시간 수정·삭제 (2) 가입자 목록(보기 전용)
- [ ] `routers/admin.py` — 전체 예약 목록 / PATCH(시간만) / DELETE / 가입자 목록, 관리자 검사
- [ ] `scripts/create_admin.py` — 명령줄로 첫 관리자 계정 생성
- [ ] `scripts/reset_password.py` — 명령줄로 특정 사용자 비밀번호 재설정
      (`python scripts/reset_password.py <이메일>` → 새 비밀번호를 화면에 안 보이게 입력받아 bcrypt 해시로 교체.
      없는 이메일이면 오류 메시지. 관리자 본인도 재설정 가능)
- [ ] pytest:
      - 남의 예약 취소 403
      - 시작된 예약 취소 거부
      - **관리자 PATCH가 같은 GPU 중복과 겹치면 409로 거부** (관리자도 예외 없음)
      - **단주기 100시간, 20일 뒤 시작 등이 관리자·일반 사용자 모두에게 허용됨** (길이·기간 제한 없음)
      - 수정 시 자기 자신과는 겹침 판정을 하지 않음
      - **사용 중인(시작이 과거인) 예약의 종료만 연장·단축하면 200**, 시작을 옮기면 400,
        종료를 지난 시각으로 보내면 400
      - **가입자 목록은 관리자만 200, 일반 사용자는 403, 비로그인은 401**
      - **가입자 목록 응답에 비밀번호 해시가 들어 있지 않음**

**완료 확인:** 일반 계정으로 남의 예약 취소·가입자 목록 조회 시도 → 거부되는 테스트 통과,
그리고 중복 금지 테스트 통과

### Phase 5 — 배포

**0) 환경 확인 (작업 시작 전)**

| 확인 명령 | 필요한 것 |
|---|---|
| `systemctl --version` | systemd (Ubuntu 기본 포함) |
| `ufw status` | 방화벽. `command not found`면 설치 필요 |
| `crontab -l` | cron. `command not found`면 설치 필요 |

없을 때 안내할 명령 (사용자가 직접 실행):
```bash
sudo apt install -y ufw cron
```

**1) 작업 목록**
- [ ] `npm run build` 결과를 FastAPI가 서빙 (SPA 폴백 포함), 프로세스 1개 / 포트 9080
- [ ] `deploy/gpu-reserve.service` — systemd (자동 시작, 비정상 종료 시 재시작)
- [ ] ufw 9080 포트 허용 안내 (sudo 명령은 직접 실행하지 않고 사용자에게 안내)
- [ ] `deploy/backup_db.sh` + 매일 실행 cron 설정
- [ ] `README.md` — 설치·실행·재시작·로그 확인·백업 복구 (초보자 기준)
- [ ] `CLAUDE.md`의 "자주 쓰는 명령어" 항목 채우기

**완료 확인:** 데스크탑 재부팅 후 휴대폰에서 `http://<IP>:9080` 접속·예약 성공

### Phase 6 — 구글 캘린더 연동

**0) 환경 확인 (작업 시작 전)**
- 파이썬 패키지 `google-api-python-client`, `google-auth-oauthlib` 설치 여부 확인
  (`pip show google-api-python-client`) → 없으면 venv 안에서 `pip install`로 설치하고 `requirements.txt`에 반영
- **사용자가 직접 해야 하는 것**: 연구실 공용 구글 계정으로 클라우드 콘솔에서 OAuth 클라이언트 만들고
  `credentials.json` 내려받기 → 단계별로 안내
- 최초 1회 OAuth 로그인은 브라우저가 필요하므로 **데스크탑 화면 앞에서** 진행해야 한다

**1) 작업 목록**
- [ ] 구글 클라우드 콘솔 설정 안내 (OAuth 클라이언트 생성, `credentials.json` 내려받기) — 단계별 안내
- [ ] 최초 1회 OAuth 로그인 스크립트 → `token.json` 저장, `.gitignore` 등록
- [ ] `google_sync_tasks` 테이블 추가
- [ ] 예약 생성 시 일정 생성 + 예약자 이메일 참석자 초대, 제목 `[서버1 GPU2 장주기] 홍길동`
- [ ] 취소 시 일정 삭제, 조기 종료·수정 시 시간 수정
- [ ] 실패해도 예약은 유지, 로그 기록 + 재시도 가능하게
- [ ] `google.enabled: false`여도 전부 정상 동작하는지 확인

**완료 확인:** 예약 시 초대 메일 도착, 취소 시 구글 캘린더에서 일정 사라짐

---

## 7. 보안·비밀 정보 (CLAUDE.md 규칙)

`.gitignore`에 반드시 포함:
```
backend/config.yaml
backend/secrets/
data/*.db
data/*.db-wal
data/*.db-shm
venv/
node_modules/
frontend/dist/
```
- 비밀번호는 bcrypt 해시로만 저장
- `sudo`가 필요한 명령(ufw, systemctl 등)은 직접 실행하지 않고 실행할 명령어를 안내
- 새 라이브러리는 `requirements.txt` / `package.json`에 즉시 반영

---

## 8. 전체 검증 방법

```bash
# 백엔드
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest                                      # Phase 1·4 자동 테스트
uvicorn app.main:app --reload --port 9081   # 개발용. http://localhost:9081/docs

# 프론트엔드 (개발 중)
cd frontend && npm install && npm run dev   # http://localhost:5173

# 배포 형태 (Phase 5 이후)
cd frontend && npm run build
uvicorn app.main:app --host 0.0.0.0 --port 9080   # http://<IP>:9080 하나로 전부
```

**수동 시나리오 점검** (Phase 3 이후 매번):
1. 가입(잘못된 코드 → 거부) → 로그인
2. 단주기 GPU 2시간 예약 → 타임라인에 빨강으로 보임
3. 같은 GPU·같은 시간 다시 예약 → "이미 예약된 시간입니다" 류의 한국어 오류
4. 장주기 GPU에 24시간 예약 시도 → 이제는 제한이 없으므로 그대로 예약됨
5. 진행 중인 예약 조기 종료 → 남은 칸이 초록으로 반환됨
6. 다른 계정으로 남의 예약 취소 시도 → 거부
7. 관리자로 남의 예약 시간을 100시간짜리로 수정 → 경고 없이 그대로 저장됨
7-1. 관리자로 **지금 사용 중인** 예약의 종료만 뒤로 미루기 → 연장됨.
     같은 예약의 시작을 과거로 옮기려 하면 거부됨
8. 관리자로 다른 예약과 겹치게 수정 시도 → 거부
9. `python scripts/reset_password.py <이메일>` 실행 후 새 비밀번호로 로그인되는지 확인
10. 휴대폰에서 접속 → 가로 스크롤만 되고 화면이 좌우로 깨지지 않음

---

## 9. 이번 범위 제외 (SPEC 12장)

- `nvidia-smi` 연동한 실사용 여부 자동 표시
- 학교 밖 외부 인터넷 접속
- 비밀번호 재설정·이메일 인증 (SPEC에 없음. 필요하면 관리자가 직접 처리)
