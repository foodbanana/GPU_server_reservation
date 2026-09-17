"""Vue 를 빌드한 결과(frontend/dist)를 FastAPI 가 함께 서빙한다 (Phase 5).

왜 필요한가:
- 개발 중에는 화면(vite, 5173)과 서버(uvicorn, 9081)를 따로 켠다.
- 운영에서는 그러면 안 된다. `npm run build` 로 만든 **완성된 화면 파일**을
  FastAPI 가 같이 내보내서, 포트 하나(9080)로 전부 동작하게 한다(SPEC 3·10장).

새로고침 문제(SPA 폴백):
  주소창에 http://IP:9080/my 를 직접 치거나 그 화면에서 F5 를 누르면,
  브라우저는 서버에 "/my 파일 주세요" 라고 묻는다. 그런 파일은 없다.
  화면 주소는 Vue 가 브라우저 안에서 처리하기 때문이다.
  그래서 **없는 파일을 물어보면 index.html 을 대신 돌려준다.** 그러면 Vue 가 켜지고,
  Vue 가 /my 화면을 그려 준다. 이것을 'SPA 폴백' 이라고 부른다.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SpaStaticFiles(StaticFiles):
    """정적 파일을 서빙하되, 없는 주소는 index.html 로 넘긴다."""

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            # /api/... 는 화면 주소가 아니라 서버 API다.
            # 없는 API를 index.html 로 돌려주면 오류를 찾기 어려워지므로 404 그대로 둔다.
            if path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def mount_frontend(app: FastAPI, static_dir: Path | None) -> None:
    """빌드된 화면 폴더를 앱에 붙인다.

    - static_dir 가 없거나(개발용 설정) 아직 빌드하지 않았으면 붙이지 않고,
      대신 "/" 로 들어왔을 때 무엇을 해야 하는지 알려 주는 안내를 보여 준다.
    - 이 함수는 라우터를 모두 등록한 **뒤에** 불러야 한다.
      (먼저 등록된 /api/... 와 /docs 가 우선이고, 남은 주소만 여기로 온다)
    """
    index_file = static_dir / "index.html" if static_dir else None

    if index_file is not None and index_file.is_file():
        app.mount("/", SpaStaticFiles(directory=static_dir, html=True), name="frontend")
        return

    if static_dir is None:
        # 개발용 설정(static_dir: "") — 화면은 vite 가 맡는다.
        안내 = (
            "이 서버는 API만 제공합니다(개발용 설정). "
            "화면은 frontend 폴더에서 `npm run dev` 를 켜고 http://localhost:5173 으로 보세요."
        )
    else:
        안내 = (
            "화면(프론트엔드) 빌드 결과를 찾지 못했습니다. "
            "frontend 폴더에서 `npm install && npm run build` 를 실행한 뒤 "
            f"서버를 다시 켜 주세요. (찾은 위치: {static_dir})"
        )

    @app.get("/", include_in_schema=False)
    def 화면_없음() -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": 안내})
