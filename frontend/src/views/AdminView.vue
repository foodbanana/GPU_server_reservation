<script setup>
// 관리자 화면 (Phase 4).
//
// - 모든 사람의 예약을 한 목록으로 본다.
// - 예약의 시작·종료 시각만 고칠 수 있다 (GPU와 예약자는 바꿀 수 없다).
// - 예약을 강제로 취소(삭제)할 수 있다. 이미 시작한 예약도 가능하다.
//
// 규칙: 다른 예약과 겹치면 관리자도 저장할 수 없다.
//       예약 길이 제한과 14일 범위 제한은 관리자만 무시할 수 있고,
//       무시하고 저장하면 서버가 경고 문구를 돌려주므로 그대로 보여 준다.
//
// 이 화면은 관리자에게만 메뉴가 보이고 주소로도 못 들어오지만,
// 그건 어디까지나 편의이고 실제 차단은 서버가 403으로 한다.
import { computed, ref } from 'vue'

import { api } from '../api/client'
import { HOURS, formatKst, kstParts, toIso } from '../utils/time'

const 예약들 = ref([])
const 불러오는중 = ref(true)
const 오류 = ref('')
const 성공 = ref('')
const 경고들 = ref([])
const 처리중ID = ref(null)

const 상태필터 = ref('active') // all / active / cancelled
const 기간필터 = ref('current') // current(아직 안 끝난 것) / all(지난 것 포함)

// 수정 중인 예약 하나 (id 와 입력값)
const 수정중 = ref(null)

// 목록을 받아올 때마다 '지금'을 다시 잡아서 예정/사용 중/끝남을 판단한다
const 지금 = ref(Date.now())

async function 불러오기() {
  불러오는중.value = true
  오류.value = ''
  지금.value = Date.now()
  try {
    예약들.value = await api.adminReservations({
      status: 상태필터.value,
      period: 기간필터.value,
    })
  } catch (e) {
    오류.value = e.message
  } finally {
    불러오는중.value = false
  }
}

불러오기()

function 필터바꿈() {
  수정중.value = null
  성공.value = ''
  경고들.value = []
  불러오기()
}

/** 'cancelled' / 'past' / 'running' / 'upcoming' — CSS 클래스 이름으로도 쓴다 */
function 상태코드(r) {
  if (r.status === 'cancelled') return 'cancelled'
  const 시작 = new Date(r.start_at).getTime()
  const 종료 = new Date(r.end_at).getTime()
  if (지금.value >= 종료) return 'past'
  if (지금.value >= 시작) return 'running'
  return 'upcoming'
}

const 상태이름표 = {
  cancelled: '취소됨',
  past: '끝남',
  running: '사용 중',
  upcoming: '예정',
}

function 상태이름(r) {
  return 상태이름표[상태코드(r)]
}

// ---------- 시간 수정 ----------

function 수정시작(r) {
  const 시작 = kstParts(new Date(r.start_at))
  const 종료 = kstParts(new Date(r.end_at))
  성공.value = ''
  경고들.value = []
  오류.value = ''
  수정중.value = {
    id: r.id,
    시작날짜: 시작.date,
    시작시: 시작.hour,
    종료날짜: 종료.date,
    종료시: 종료.hour,
  }
}

function 수정취소() {
  수정중.value = null
}

const 수정길이 = computed(() => {
  const m = 수정중.value
  if (!m) return 0
  const ms =
    new Date(toIso(m.종료날짜, m.종료시)) - new Date(toIso(m.시작날짜, m.시작시))
  return Math.round(ms / 3600000)
})

async function 저장하기(r) {
  const m = 수정중.value
  오류.value = ''
  성공.value = ''
  경고들.value = []
  처리중ID.value = r.id
  try {
    const 결과 = await api.adminUpdateReservation(r.id, {
      start_at: toIso(m.시작날짜, m.시작시),
      end_at: toIso(m.종료날짜, m.종료시),
    })
    성공.value =
      `${결과.reservation.user_name} 님의 예약을 바꿨습니다. ` +
      `(${결과.reservation.gpu_label} / ${formatKst(결과.reservation.start_at)} ~ ${formatKst(결과.reservation.end_at)})`
    // 관리자가 규칙을 무시하고 저장한 경우에만 내용이 들어 있다
    경고들.value = 결과.warnings ?? []
    수정중.value = null
    await 불러오기()
  } catch (e) {
    // 겹치는 예약(409)이나 규칙 위반(400) 메시지를 서버가 한국어로 보내 준다
    오류.value = e.message
  } finally {
    처리중ID.value = null
  }
}

// ---------- 삭제(강제 취소) ----------

async function 삭제하기(r) {
  const 물음 =
    `${r.user_name} 님의 예약을 취소할까요?\n\n${r.gpu_label}\n` +
    `${formatKst(r.start_at)} ~ ${formatKst(r.end_at)}\n\n` +
    '이 시간은 다른 사람이 예약할 수 있게 됩니다. 되돌릴 수 없습니다.'
  if (!window.confirm(물음)) return

  오류.value = ''
  성공.value = ''
  경고들.value = []
  처리중ID.value = r.id
  try {
    const 결과 = await api.adminDeleteReservation(r.id)
    성공.value = `${결과.user_name} 님의 예약을 취소했습니다. (${결과.gpu_label})`
    수정중.value = null
    await 불러오기()
  } catch (e) {
    오류.value = e.message
  } finally {
    처리중ID.value = null
  }
}
</script>

<template>
  <h1>관리자 — 전체 예약</h1>
  <p class="hint intro">
    예약의 시작·종료 시각만 고칠 수 있습니다 (GPU와 예약자는 바꿀 수 없습니다).<br />
    다른 예약과 시간이 겹치면 관리자도 저장할 수 없고, 예약 길이·14일 제한만 무시할 수 있습니다.
  </p>

  <div class="card filters">
    <label>
      상태
      <select v-model="상태필터" @change="필터바꿈">
        <option value="active">유효한 예약</option>
        <option value="cancelled">취소된 예약</option>
        <option value="all">전체</option>
      </select>
    </label>
    <label>
      기간
      <select v-model="기간필터" @change="필터바꿈">
        <option value="current">아직 안 끝난 예약</option>
        <option value="all">지난 예약 포함</option>
      </select>
    </label>
    <button class="btn-secondary" @click="필터바꿈">새로고침</button>
  </div>

  <p v-if="오류" class="error-box">{{ 오류 }}</p>
  <p v-if="성공" class="success-box">{{ 성공 }}</p>
  <p v-if="경고들.length" class="warn-box">
    ⚠ 규칙을 무시하고 저장했습니다.
    <span v-for="(w, i) in 경고들" :key="i" class="warn-line">{{ w }}</span>
  </p>

  <p v-if="불러오는중" class="hint">불러오는 중…</p>
  <p v-else-if="예약들.length === 0" class="card hint empty">조건에 맞는 예약이 없습니다.</p>

  <div v-else class="list">
    <div v-for="r in 예약들" :key="r.id" class="card item">
      <div class="head">
        <div>
          <div class="gpu">{{ r.gpu_label }}</div>
          <div class="who">{{ r.user_name }} <span class="email">{{ r.user_email }}</span></div>
          <div class="time">{{ formatKst(r.start_at) }} ~ {{ formatKst(r.end_at) }}</div>
        </div>
        <div class="right">
          <span class="badge" :class="상태코드(r)">{{ 상태이름(r) }}</span>
          <div v-if="r.status !== 'cancelled'" class="buttons">
            <button
              class="btn-secondary small"
              :disabled="처리중ID === r.id"
              @click="수정중?.id === r.id ? 수정취소() : 수정시작(r)"
            >
              {{ 수정중?.id === r.id ? '접기' : '시간 수정' }}
            </button>
            <button
              class="btn-secondary small danger"
              :disabled="처리중ID === r.id"
              @click="삭제하기(r)"
            >
              삭제
            </button>
          </div>
        </div>
      </div>

      <!-- 시간 수정 폼 -->
      <form v-if="수정중?.id === r.id" class="edit" @submit.prevent="저장하기(r)">
        <div class="field">
          <label>시작</label>
          <div class="datetime">
            <input v-model="수정중.시작날짜" type="date" required />
            <select v-model.number="수정중.시작시">
              <option v-for="h in HOURS" :key="h" :value="h">
                {{ String(h).padStart(2, '0') }}:00
              </option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>종료</label>
          <div class="datetime">
            <input v-model="수정중.종료날짜" type="date" required />
            <select v-model.number="수정중.종료시">
              <option v-for="h in HOURS" :key="h" :value="h">
                {{ String(h).padStart(2, '0') }}:00
              </option>
            </select>
          </div>
        </div>
        <p class="length">
          바꿀 길이: <strong>{{ 수정길이 }}시간</strong>
        </p>
        <div class="edit-buttons">
          <button class="btn-primary" type="submit" :disabled="처리중ID === r.id">
            {{ 처리중ID === r.id ? '저장 중…' : '저장' }}
          </button>
          <button class="btn-secondary" type="button" @click="수정취소">취소</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
h1 {
  font-size: 1.25rem;
  margin: 0 0 0.4rem;
}

.intro {
  line-height: 1.6;
  margin-bottom: 1rem;
}

.filters {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.9rem 1rem;
  margin-bottom: 1rem;
}

.filters label {
  font-size: 0.85rem;
  font-weight: 600;
  display: grid;
  gap: 0.3rem;
}

.filters select {
  min-width: 10rem;
}

.filters button {
  padding: 0.5rem 0.9rem;
  font-size: 0.9rem;
}

.item {
  padding: 0.9rem 1rem;
  margin-bottom: 0.5rem;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.gpu {
  font-weight: 600;
}

.who {
  font-size: 0.9rem;
  margin-top: 0.15rem;
}

.email {
  color: var(--muted);
  font-size: 0.8rem;
}

.time {
  font-size: 0.9rem;
  margin-top: 0.15rem;
  color: var(--muted);
}

.right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.buttons {
  display: flex;
  gap: 0.4rem;
}

.small {
  padding: 0.4rem 0.7rem;
  font-size: 0.85rem;
  white-space: nowrap;
}

.danger {
  color: var(--red);
  border-color: #f0b8b6;
}

/* 상태 표시 (타임라인 화면과 같은 색 규칙) */
.badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  white-space: nowrap;
}

.badge.upcoming {
  background: #fdecea;
  color: var(--red);
}

.badge.running {
  background: #fff8e1;
  color: #8a6100;
}

.badge.past,
.badge.cancelled {
  background: #eef1f5;
  color: var(--muted);
}

.edit {
  margin-top: 0.9rem;
  padding-top: 0.9rem;
  border-top: 1px solid var(--gray-line);
}

.datetime {
  display: flex;
  gap: 0.5rem;
}

.datetime input {
  flex: 2 1 0;
  min-width: 0;
}

.datetime select {
  flex: 1 1 0;
  min-width: 0;
}

.length {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
}

.edit-buttons {
  display: flex;
  gap: 0.5rem;
}

.warn-box {
  background: #fff8e1;
  border: 1px solid #f0d58c;
  color: #8a6100;
  border-radius: 6px;
  padding: 0.75rem 0.9rem;
  margin: 0.75rem 0;
  line-height: 1.6;
}

.warn-line {
  display: block;
}

.empty {
  margin: 0;
}
</style>
