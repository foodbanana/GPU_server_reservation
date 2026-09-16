<script setup>
// 내 예약 목록 화면 (Phase 4).
//
// - 예약을 '사용 중 / 예정 / 지난' 세 묶음으로 나눠 보여 준다.
// - 아직 시작하지 않은 예약: [취소] 버튼
// - 지금 사용 중인 예약: [조기 종료] 버튼 (남은 시간을 반납한다)
// 두 버튼 모두 누르기 전에 확인 창이 한 번 뜬다. 진짜 판정은 서버가 한다.
import { computed, onUnmounted, ref } from 'vue'

import { api } from '../api/client'
import { formatKst } from '../utils/time'

const 예약들 = ref([])
const 불러오는중 = ref(true)
const 오류 = ref('')
const 성공 = ref('')
const 처리중ID = ref(null)

// 시간이 지나면 '예정' 이던 예약이 '사용 중'으로 바뀌어야 하므로 1분마다 현재 시각을 갱신한다.
const 지금 = ref(Date.now())
const 타이머 = setInterval(() => (지금.value = Date.now()), 60 * 1000)
onUnmounted(() => clearInterval(타이머))

async function 불러오기() {
  오류.value = ''
  try {
    예약들.value = await api.myReservations()
  } catch (e) {
    오류.value = e.message
  } finally {
    불러오는중.value = false
  }
}

불러오기()

/** 예약 하나의 상태: 'running'(사용 중) / 'upcoming'(예정) / 'past'(지난) / 'cancelled'(취소됨) */
function 상태(r) {
  if (r.status === 'cancelled') return 'cancelled'
  const 시작 = new Date(r.start_at).getTime()
  const 종료 = new Date(r.end_at).getTime()
  if (지금.value >= 종료) return 'past'
  if (지금.value >= 시작) return 'running'
  return 'upcoming'
}

function 길이시간(r) {
  return Math.round((new Date(r.end_at) - new Date(r.start_at)) / 3600000)
}

function 정렬(목록, 오름차순) {
  return [...목록].sort((a, b) =>
    오름차순
      ? new Date(a.start_at) - new Date(b.start_at)
      : new Date(b.start_at) - new Date(a.start_at),
  )
}

const 사용중 = computed(() => 정렬(예약들.value.filter((r) => 상태(r) === 'running'), true))
const 예정 = computed(() => 정렬(예약들.value.filter((r) => 상태(r) === 'upcoming'), true))
// 지난 예약과 취소한 예약은 한 묶음으로, 최근 것부터
const 지난것 = computed(() =>
  정렬(
    예약들.value.filter((r) => ['past', 'cancelled'].includes(상태(r))),
    false,
  ),
)

const 비어있음 = computed(
  () => !불러오는중.value && 예약들.value.length === 0,
)

// ---------- 취소 / 조기 종료 ----------

async function 취소하기(r) {
  const 물음 =
    `이 예약을 취소할까요?\n\n${r.gpu_label}\n` +
    `${formatKst(r.start_at)} ~ ${formatKst(r.end_at)}\n\n` +
    '취소하면 이 시간은 다른 사람이 예약할 수 있게 됩니다.'
  if (!window.confirm(물음)) return
  await 실행(r, () => api.cancelReservation(r.id), '예약을 취소했습니다.')
}

async function 조기종료하기(r) {
  const 물음 =
    `사용 중인 이 예약을 지금 끝낼까요?\n\n${r.gpu_label}\n` +
    `${formatKst(r.start_at)} ~ ${formatKst(r.end_at)}\n\n` +
    '종료 시각이 다음 정시로 당겨지고, 남은 시간은 다른 사람이 쓸 수 있게 됩니다.\n' +
    '한 번 끝내면 되돌릴 수 없습니다.'
  if (!window.confirm(물음)) return
  await 실행(r, () => api.endReservationNow(r.id), '예약을 조기 종료했습니다.')
}

async function 실행(r, 부르기, 성공문구) {
  오류.value = ''
  성공.value = ''
  처리중ID.value = r.id
  try {
    const 결과 = await 부르기()
    성공.value = `${성공문구} (${결과.gpu_label} / ${formatKst(결과.start_at)} ~ ${formatKst(결과.end_at)})`
    await 불러오기()
  } catch (e) {
    // 서버가 보내 준 한국어 메시지를 그대로 (예: "이미 시작된 예약은 취소할 수 없습니다.")
    오류.value = e.message
    await 불러오기()
  } finally {
    처리중ID.value = null
  }
}
</script>

<template>
  <h1>내 예약</h1>

  <p v-if="오류" class="error-box">{{ 오류 }}</p>
  <p v-if="성공" class="success-box">{{ 성공 }}</p>

  <p v-if="불러오는중" class="hint">불러오는 중…</p>
  <p v-else-if="비어있음" class="card hint empty">
    아직 예약이 없습니다. 위의 ‘예약 신청’ 메뉴에서 GPU를 예약해 보세요.
  </p>

  <template v-else>
    <!-- 지금 사용 중 -->
    <section v-if="사용중.length" class="group">
      <h2><span class="dot running"></span>사용 중 ({{ 사용중.length }})</h2>
      <div v-for="r in 사용중" :key="r.id" class="card row">
        <div class="info">
          <div class="gpu">{{ r.gpu_label }}</div>
          <div class="time">{{ formatKst(r.start_at) }} ~ {{ formatKst(r.end_at) }}</div>
          <div class="hint">{{ 길이시간(r) }}시간 예약 · 지금 사용 중</div>
        </div>
        <button
          class="btn-secondary danger"
          :disabled="처리중ID === r.id"
          @click="조기종료하기(r)"
        >
          조기 종료
        </button>
      </div>
    </section>

    <!-- 앞으로 쓸 예약 -->
    <section v-if="예정.length" class="group">
      <h2><span class="dot upcoming"></span>예정 ({{ 예정.length }})</h2>
      <div v-for="r in 예정" :key="r.id" class="card row">
        <div class="info">
          <div class="gpu">{{ r.gpu_label }}</div>
          <div class="time">{{ formatKst(r.start_at) }} ~ {{ formatKst(r.end_at) }}</div>
          <div class="hint">{{ 길이시간(r) }}시간 예약 · 아직 시작 전</div>
        </div>
        <button
          class="btn-secondary danger"
          :disabled="처리중ID === r.id"
          @click="취소하기(r)"
        >
          취소
        </button>
      </div>
    </section>

    <!-- 지난 예약 + 취소한 예약 -->
    <section v-if="지난것.length" class="group">
      <h2><span class="dot past"></span>지난 예약 ({{ 지난것.length }})</h2>
      <div v-for="r in 지난것" :key="r.id" class="card row faded">
        <div class="info">
          <div class="gpu">{{ r.gpu_label }}</div>
          <div class="time">{{ formatKst(r.start_at) }} ~ {{ formatKst(r.end_at) }}</div>
          <div class="hint">
            {{ r.status === 'cancelled' ? '취소된 예약' : '끝난 예약' }}
          </div>
        </div>
      </div>
    </section>
  </template>
</template>

<style scoped>
h1 {
  font-size: 1.25rem;
  margin: 0 0 1rem;
}

h2 {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.95rem;
  margin: 0 0 0.5rem;
}

.group {
  margin-bottom: 1.5rem;
}

/* 상태 색은 타임라인 화면과 같은 규칙 (SPEC 7장) */
.dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  display: inline-block;
}

.dot.running {
  background: #f9a825;
}

.dot.upcoming {
  background: var(--red);
}

.dot.past {
  background: #b0b7c3;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  margin-bottom: 0.5rem;
}

.row.faded {
  background: #fafbfc;
  color: var(--muted);
}

.info {
  min-width: 0;
}

.gpu {
  font-weight: 600;
}

.time {
  font-size: 0.9rem;
  margin-top: 0.15rem;
}

.row .hint {
  margin-top: 0.15rem;
}

.danger {
  color: var(--red);
  border-color: #f0b8b6;
  white-space: nowrap;
  flex: none;
}

.empty {
  margin: 0;
}

@media (max-width: 480px) {
  .row {
    align-items: flex-start;
  }
}
</style>
