"""config.yaml 을 기준으로 GPU 12장을 DB에 등록·갱신한다 (SPEC 4장).

앱을 켤 때마다 실행된다.
- DB에 없는 GPU는 추가
- model / category 가 설정과 달라졌으면 갱신 (서버3 A100/maxQ 번호가 반대일 때 대비)
- 설정에서 빠진 GPU는 예약 기록이 얽혀 있을 수 있으므로 지우지 않고 그대로 둔다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Config, get_config
from app.models import Gpu


def seed_gpus(db: Session, config: Config | None = None) -> None:
    config = config or get_config()

    # 타임라인 행 순서: 단주기 6개 먼저, 그다음 장주기 6개 (SPEC 8장)
    ordered = sorted(
        config.gpus,
        key=lambda g: (0 if g.category == "short" else 1, g.server_no, g.gpu_index),
    )

    for order, spec in enumerate(ordered):
        gpu = db.scalar(
            select(Gpu).where(
                Gpu.server_no == spec.server_no, Gpu.gpu_index == spec.gpu_index
            )
        )
        if gpu is None:
            db.add(
                Gpu(
                    server_no=spec.server_no,
                    gpu_index=spec.gpu_index,
                    model=spec.model,
                    category=spec.category,
                    sort_order=order,
                )
            )
        else:
            gpu.model = spec.model
            gpu.category = spec.category
            gpu.sort_order = order

    db.commit()
