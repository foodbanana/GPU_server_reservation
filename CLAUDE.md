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

(Phase 2가 끝나면 프론트엔드 명령어를 여기에 추가할 것)
