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

## 자주 쓰는 명령어

> **주의:** 이 컴퓨터는 ROS(`/opt/ros/jazzy`)가 `PYTHONPATH`에 들어 있어서
> pytest가 ROS 플러그인을 잘못 읽고 오류를 낸다.
> 그래서 아래 명령에는 `PYTHONPATH=` 를 붙여 ROS 경로를 잠깐 비운다.

### 처음 한 번만 (설치)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # 그다음 invite_code, jwt_secret 채우기
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # jwt_secret 만들기
```

### 테스트 실행
```bash
cd backend
PYTHONPATH= venv/bin/python -m pytest          # 전체
PYTHONPATH= venv/bin/python -m pytest -v       # 테스트 이름까지 보기
PYTHONPATH= venv/bin/python -m pytest tests/test_overlap.py   # 파일 하나만
```

### 서버 실행
```bash
cd backend
PYTHONPATH= venv/bin/python -m uvicorn app.main:app --reload --port 8000
# 브라우저에서 http://localhost:8000/docs  (API를 직접 눌러볼 수 있는 화면)
# 다른 기기에서 접속하려면 --host 0.0.0.0 을 추가
```

### DB 초기화 (처음부터 다시)
```bash
rm -f data/gpu.db data/gpu.db-wal data/gpu.db-shm   # 서버를 끈 상태에서
```

### 타임라인 화면 확인용 데모 데이터 (Phase 3)

진짜 DB(`data/gpu.db`)는 **건드리지 않는다.** `backend/demo/` 폴더에 데모 전용 설정과 DB를
따로 만들어서 거기에만 가짜 예약을 넣는다. (`backend/demo/` 는 git에 올라가지 않는다)

```bash
cd backend
PYTHONPATH= venv/bin/python scripts/seed_demo.py      # 데모 DB + 예약 16건 만들기 (다시 실행하면 새로 만듦)
```

그다음 **데모 설정으로** 서버를 켠다 (평소 명령과 달리 앞에 `GPU_RESERVE_CONFIG=` 가 붙는다):

```bash
cd backend
GPU_RESERVE_CONFIG=demo/config.yaml PYTHONPATH= \
  venv/bin/python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

데모 로그인: `minjun@example.com` / 비밀번호 `demo1234` (다른 계정은 스크립트 실행 결과에 나온다)

데모를 지우고 싶으면 폴더째 지우면 된다: `rm -rf backend/demo`

---

## 프론트엔드 (Phase 2~)

Node.js **v24.21.0**, npm **11.19.0** 사용.

### 처음 한 번만 (설치)
```bash
cd frontend
npm install
```

### 개발 중에는 터미널 2개를 띄운다

**터미널 1 — 백엔드 (포트 8000)**
```bash
cd backend
PYTHONPATH= venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

**터미널 2 — 프론트엔드 (포트 5173)**
```bash
cd frontend
npm run dev
```

그다음 브라우저에서 **http://localhost:5173** 접속.
화면에서 부르는 `/api/...` 요청은 vite 가 8000번 백엔드로 대신 넘겨준다(vite.config.js 의 proxy).
**백엔드를 먼저 켜야 한다.** 안 켜져 있으면 "서버에 연결할 수 없습니다" 오류가 뜬다.

### 휴대폰에서 확인할 때
```bash
ip addr | grep "inet "      # 데스크탑 IP 확인
# 휴대폰 브라우저에서 http://<데스크탑IP>:5173
```
휴대폰이 없어도 PC 크롬에서 **F12 → 왼쪽 위 휴대폰 모양 아이콘(Ctrl+Shift+M)** 을 누르면
휴대폰 화면 크기로 볼 수 있다. (iPhone 14 / Galaxy S20 등 선택)

### 빌드 (Phase 5 배포용 미리보기)
```bash
cd frontend
npm run build      # 결과가 frontend/dist 에 생긴다
npm run preview
```

### 로그인이 꼬였을 때
브라우저 개발자도구(F12) → Application → Local Storage → `gpu-reserve-token` 삭제
