<script setup>
// 관리자 화면 (Phase 4).
//
// 탭 두 개로 나뉜다.
//  1) 전체 예약 — 모든 사람의 예약을 보고, 시작·종료 시각을 고치거나 강제 취소한다.
//  2) 가입자   — 가입한 사람 목록을 본다. 보기 전용이라 고치거나 지우는 버튼은 없다.
//
// 규칙: 다른 예약과 겹치면 관리자도 저장할 수 없다.
//       예약 길이 제한과 '14일 이내 시작' 제한은 없어졌으므로,
//       관리자만 무시할 수 있는 규칙도 이제 없다.
//
// 이 화면은 관리자에게만 메뉴가 보이고 주소로도 못 들어오지만,
// 그건 어디까지나 편의이고 실제 차단은 서버가 403으로 한다.
import { computed, ref } from 'vue'

import { api } from '../api/client'
import { HOURS, formatKst, kstParts, toIso } from '../utils/time'

const 탭 = ref('reservations') // reservations / users

const 예약들 = ref([])
const 불러오는중 = ref(true)
const 오류 = ref('')
const 성공 = ref('')
const 처리중ID = ref(null)

const 상태필터 = ref('active') // all / active / cancelled
const 기간필터 = ref('current') // current(아직 안 끝난 것) / all(지난 것 포함)

// 수정 중인 예약 하나 (id 와 입력값)
const 수정중 = ref(null)

// 목록을 받아올 때마다 '지금'을 다시 잡아서 예정/사용 중/끝남을 판단한다
const 지금 = ref(Date.now())

// ---------- 전체 예약 ----------

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
  처리중ID.value = r.id
  try {
    const 결과 = await api.adminUpdateReservation(r.id, {
      start_at: toIso(m.시작날짜, m.시작시),
      end_at: toIso(m.종료날짜, m.종료시),
    })
    성공.value =
      `${결과.user_name} 님의 예약을 바꿨습니다. ` +
      `(${결과.gpu_label} / ${formatKst(결과.start_at)} ~ ${formatKst(결과.end_at)})`
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

// ---------- 가입자 목록 (보기 전용) ----------

const 가입자들 = ref([])
const 가입자불러오는중 = ref(false)
const 가입자오류 = ref('')

async function 가입자불러오기() {
  가입자불러오는중.value = true
  가입자오류.value = ''
  try {
    가입자들.value = await api.adminUsers()
  } catch (e) {
    가입자오류.value = e.message
  } finally {
    가입자불러오는중.value = false
  }
}

function 탭바꾸기(이름) {
  탭.value = 이름
  성공.value = ''
  오류.value = ''
  수정중.value = null
  if (이름 === 'users' && 가입자들.value.length === 0) 가입자불러오기()
}

/** 가입일은 시각까지 볼 필요가 없어서 날짜만 보여 준다 */
function 가입일(iso) {
  return formatKst(iso).slice(0, 10)
}
</script>

<template>
  <h1>관리자</h1>

  <div class="tabs">
    <button
      class="tab"
      :class="{ on: 탭 === 'reservations' }"
      @click="탭바꾸기('reservations')"
    >
      전체 예약
    </button>
    <button class="tab" :class="{ on: 탭 === 'users' }" @click="탭바꾸기('users')">
      가입자
    </button>
  </div>

  <!-- ================= 전체 예약 ================= -->
  <template v-if="탭 === 'reservations'">
    <p class="hint intro">
      예약의 시작·종료 시각만 고칠 수 있습니다 (GPU와 예약자는 바꿀 수 없습니다).<br />
      다른 예약과 시간이 겹치면 관리자도 저장할 수 없습니다. 예약 길이·기간 제한은 없습니다.<br />
      사용 중인 예약도 <strong>시작을 그대로 두고 종료 시각만</strong> 바꾸면 연장할 수 있습니다.
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
          <p v-if="상태코드(r) !== 'upcoming'" class="hint edit-note">
            이미 시작된 예약입니다. <strong>시작은 그대로 두고 종료 시각만</strong> 바꾸면
            연장하거나 앞당길 수 있습니다. (시작을 지난 시각으로 옮기는 것은 막혀 있습니다)
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

  <!-- ================= 가입자 ================= -->
  <template v-else>
    <p class="hint intro">
      가입한 사람 목록입니다. <strong>보기 전용</strong>이라 여기서 계정을 고치거나 지울 수는
      없습니다.<br />
      관리자 권한을 주고 빼거나 비밀번호를 재설정하려면 서버에서
      <code>scripts/set_admin.py</code>, <code>scripts/reset_password.py</code> 를 씁니다.
    </p>

    <div class="card filters">
      <span class="count">모두 {{ 가입자들.length }}명</span>
      <button class="btn-secondary" :disabled="가입자불러오는중" @click="가입자불러오기">
        새로고침
      </button>
    </div>

    <p v-if="가입자오류" class="error-box">{{ 가입자오류 }}</p>
    <p v-if="가입자불러오는중" class="hint">불러오는 중…</p>
    <p v-else-if="가입자들.length === 0" class="card hint empty">가입한 사람이 없습니다.</p>

    <div v-else class="card table-card">
      <div class="table-scroll">
        <table class="users">
          <thead>
            <tr>
              <th>이름</th>
              <th>이메일</th>
              <th>권한</th>
              <th>가입일</th>
              <th class="num">현재·예정 예약</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in 가입자들" :key="u.id">
              <td class="name">{{ u.name }}</td>
              <td class="email-cell">{{ u.email }}</td>
              <td>
                <span v-if="u.is_admin" class="badge admin">관리자</span>
                <span v-else class="badge normal">일반</span>
              </td>
              <td class="joined">{{ 가입일(u.created_at) }}</td>
              <td class="num">
                <strong :class="{ zero: u.active_reservation_count === 0 }">
                  {{ u.active_reservation_count }}
                </strong>
                건
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="hint note">
        '현재·예정 예약'은 지금 사용 중이거나 앞으로 잡혀 있는 예약 수입니다.
        (취소했거나 이미 끝난 예약은 세지 않습니다)
      </p>
    </div>
  </template>
</template>

<style scoped>
h1 {
  font-size: 1.25rem;
  margin: 0 0 0.75rem;
}

/* 탭 */
.tabs {
  display: flex;
  gap: 0.35rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--gray-line);
}

.tab {
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  padding: 0.55rem 0.9rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--muted);
}

.tab.on {
  color: #1a73e8;
  border-bottom-color: #1a73e8;
}

.intro {
  line-height: 1.6;
  margin-bottom: 1rem;
}

.intro code {
  background: #eef1f5;
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
  font-size: 0.85em;
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

.count {
  font-size: 0.9rem;
  font-weight: 600;
  margin-right: auto;
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
  display: inline-block;
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
.badge.cancelled,
.badge.normal {
  background: #eef1f5;
  color: var(--muted);
}

.badge.admin {
  background: #e6effc;
  color: #1a53a8;
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
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
}

.edit-note {
  margin: 0 0 0.75rem;
  line-height: 1.5;
}

.edit-buttons {
  display: flex;
  gap: 0.5rem;
}

.empty {
  margin: 0;
}

/* ---------- 가입자 표 ---------- */
.table-card {
  padding: 0.5rem 0.5rem 0.75rem;
}

/* 휴대폰에서 표가 넘치면 이 상자 안에서만 좌우로 밀린다 */
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.users {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
  white-space: nowrap;
}

.users th,
.users td {
  padding: 0.6rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid var(--gray-line);
}

.users th {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 700;
}

.users tbody tr:last-child td {
  border-bottom: none;
}

.users .name {
  font-weight: 600;
}

.users .email-cell,
.users .joined {
  color: var(--muted);
}

.users .num {
  text-align: right;
}

.users .num strong {
  font-size: 1rem;
}

.users .num strong.zero {
  color: var(--muted);
  font-weight: 500;
}

.note {
  margin: 0.6rem 0.4rem 0;
  line-height: 1.5;
}
</style>
