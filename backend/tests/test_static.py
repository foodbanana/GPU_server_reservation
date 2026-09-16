"""빌드된 화면(frontend/dist) 서빙 검사 (Phase 5).

운영에서는 포트 하나(8000)로 화면과 API를 모두 내보낸다.
확인할 것:
  1) "/" 로 들어오면 index.html 이 나온다
  2) 주소창에 /my 를 직접 치거나 새로고침해도 index.html 이 나온다 (SPA 폴백)
  3) 없는 /api/... 는 index.html 이 아니라 404 가 나온다 (오류를 찾기 쉽게)
  4) 빌드하지 않았으면 무엇을 해야 하는지 안내가 나온다
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static_files import mount_frontend

INDEX_HTML = "<!DOCTYPE html><html><head><title>연구실 GPU 예약</title></head><body></body></html>"


def 앱만들기(static_dir: Path | None) -> FastAPI:
    """라우터가 붙은 앱을 흉내 낸다 (/api/... 가 먼저, 화면이 나중)."""
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_frontend(app, static_dir)
    return app


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """`npm run build` 결과를 흉내 낸 임시 폴더."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log('hi')", encoding="utf-8")
    return dist


def test_루트는_index_html을_돌려준다(dist_dir: Path) -> None:
    with TestClient(앱만들기(dist_dir)) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "연구실 GPU 예약" in response.text


def test_빌드된_js_파일을_돌려준다(dist_dir: Path) -> None:
    with TestClient(앱만들기(dist_dir)) as client:
        response = client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "console.log" in response.text


@pytest.mark.parametrize("path", ["/my", "/admin", "/reserve/3", "/login", "/signup"])
def test_화면_주소는_새로고침해도_index_html이_나온다(dist_dir: Path, path: str) -> None:
    """Vue 가 처리하는 주소는 서버에 파일이 없다. index.html 로 넘겨야 화면이 뜬다."""
    with TestClient(앱만들기(dist_dir)) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert "연구실 GPU 예약" in response.text


def test_api는_화면보다_우선한다(dist_dir: Path) -> None:
    with TestClient(앱만들기(dist_dir)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_없는_api는_index_html이_아니라_404(dist_dir: Path) -> None:
    """주소를 잘못 적었을 때 화면이 나오면 원인을 찾기 어렵다."""
    with TestClient(앱만들기(dist_dir)) as client:
        response = client.get("/api/없는주소")
    assert response.status_code == 404
    assert "연구실 GPU 예약" not in response.text


def test_빌드하지_않았으면_안내를_보여준다(tmp_path: Path) -> None:
    with TestClient(앱만들기(tmp_path / "없는dist")) as client:
        response = client.get("/")
    assert response.status_code == 503
    assert "npm run build" in response.json()["detail"]


def test_static_dir가_없으면_api만_제공한다() -> None:
    """개발용 설정(static_dir: "")에서는 화면을 서빙하지 않고, 그렇다고 안내한다."""
    with TestClient(앱만들기(None)) as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/")
    assert response.status_code == 503
    assert "npm run dev" in response.json()["detail"]
