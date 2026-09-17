<script setup>
// 메인 화면: 2주치 예약 현황 타임라인 (SPEC 8장 2번).
//
// 표는 '기준날짜 0시'부터 일수(기본 14일)만큼 그린다.
// 기준날짜를 앞뒤로 옮기는 버튼이 있어서 2주 뒤, 4주 뒤 예약도 볼 수 있다.
// 1분마다 현재 시각과 예약 목록을 새로 받아서 세로선과 색이 저절로 맞춰지게 한다.

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import TimelineGrid from '../components/TimelineGrid.vue'
import { api } from '../api/client'
import { addHours, formatKst, kstParts, shortDate, toIso } from '../utils/time'

const 기본일수 = 14

const gpus = ref([])
const 예약 = ref([])
const 일수 = ref(기본일수)
const 지금 = ref(new Date())
/** 표의 왼쪽 끝 날짜. 기본은 오늘. 버튼으로 앞뒤 2주씩 옮긴다. */
const 기준날짜 = ref(kstParts().date)
const 불러오는중 = ref(true)
const 오류 = ref('')
const 마지막갱신 = ref(null)

const grid = ref(null)

let 타이머 = null

/** 조회 범위: 기준날짜 0시 ~ 일수 뒤 0시 */
const 조회범위 = computed(() => ({
  start: toIso(기준날짜.value, 0),
  end: toIso(addHours(기준날짜.value, 0, 일수.value * 24).date, 0),
}))

/** 오늘 날짜(한국 시간). 지금 보고 있는 화면이 오늘을 담고 있는지 판단할 때 쓴다. */
const 오늘 = computed(() => kstParts(지금.value).date)

const 마지막날짜 = computed(() => addHours(기준날짜.value, 0, 일수.value * 24 - 1).date)

/** 이동 버튼에 쓸 말. 14일이면 '2주', 7의 배수가 아니면 '10일' 처럼 나온다. */
const 이동단위 = computed(() =>
  일수.value % 7 === 0 ? `${일수.value / 7}주` : `${일수.value}일`,
)

/** 지금 보고 있는 기간에 오늘이 들어 있는가 */
const 오늘이보임 = computed(
  () => 오늘.value >= 기준날짜.value && 오늘.value <= 마지막날짜.value,
)

const 기간문구 = computed(
  () => `${shortDate(기준날짜.value)} ~ ${shortDate(마지막날짜.value)}`,
)

async function 불러오기({ 처음 = false } = {}) {
  if (처음) 불러오는중.value = true
  지금.value = new Date()
  try {
    // 설정값(timeline_days)이 14가 아니면 그 값에 맞춰 표를 그린다
    if (처음) {
      const 설정 = await api.config()
      일수.value = 설정?.timeline_days ?? 기본일수
    }
    const [목록, 예약목록] = await Promise.all([
      처음 ? api.gpus() : Promise.resolve(gpus.value),
      api.reservations(조회범위.value.start, 조회범위.value.end),
    ])
    gpus.value = 목록
    예약.value = 예약목록
    마지막갱신.value = new Date()
    오류.value = ''
  } catch (e) {
    오류.value = e.message
  } finally {
    불러오는중.value = false
  }
}

// ---------- 기간 이동 ----------

function 옮기기(일) {
  기준날짜.value = addHours(기준날짜.value, 0, 일 * 24).date
}

function 오늘로() {
  기준날짜.value = kstParts().date
  // 이미 오늘 화면이면 기준날짜가 그대로여서 watch 가 안 걸리므로 여기서 스크롤한다
  grid.value?.지금으로스크롤()
}

// 기간을 옮기면 그 기간의 예약을 새로 받아 온다
watch(기준날짜, () => {
  불러오기()
})

onMounted(() => {
  불러오기({ 처음: true })
  // 1분마다 현재 시각 세로선과 예약 목록을 갱신한다 (보고 있는 기간은 그대로 둔다)
  타이머 = setInterval(() => 불러오기(), 60 * 1000)
})

onBeforeUnmount(() => {
  if (타이머) clearInterval(타이머)
})

const 갱신시각 = computed(() =>
  마지막갱신.value ? formatKst(마지막갱신.value.toISOString()) : '',
)
</script>

<template>
  <div class="head">
    <div>
      <h1>예약 현황</h1>
      <p class="hint">
        1칸 = 1시간 · GPU 줄을 누르면 그 GPU 예약 화면으로 갑니다. 예약 기간 제한은 없으니
        더 먼 미래는 <strong>다음 {{ 이동단위 }}</strong> 로 넘겨 보세요.
      </p>
    </div>
    <div class="head-actions">
      <button class="btn-secondary small" :disabled="불러오는중" @click="옮기기(-일수)">
        ← 이전 {{ 이동단위 }}
      </button>
      <button class="btn-secondary small" :disabled="불러오는중" @click="오늘로">오늘로</button>
      <button class="btn-secondary small" :disabled="불러오는중" @click="옮기기(일수)">
        다음 {{ 이동단위 }} →
      </button>
      <button class="btn-secondary small" :disabled="불러오는중" @click="불러오기()">
        새로고침
      </button>
    </div>
  </div>

  <p class="period">
    보고 있는 기간: <strong>{{ 기간문구 }}</strong>
    <span v-if="!오늘이보임" class="not-today">오늘이 아닌 기간을 보고 있습니다</span>
  </p>

  <ul class="legend">
    <li><span class="sw free" />예약 가능</li>
    <li><span class="sw booked" />예약됨</li>
    <li><span class="sw using" />사용 중</li>
    <li><span class="sw past" />지난 시간</li>
    <li><span class="sw nowline" />현재 시각</li>
  </ul>

  <p v-if="오류" class="error-box">{{ 오류 }}</p>
  <p v-if="불러오는중" class="hint">불러오는 중…</p>

  <TimelineGrid
    v-else
    ref="grid"
    :gpus="gpus"
    :reservations="예약"
    :now="지금"
    :days="일수"
    :start-date="기준날짜"
  />

  <p v-if="갱신시각" class="hint updated">
    {{ 갱신시각 }} 기준 (1분마다 자동 갱신) · 좌우로 밀어서 다른 날짜를 볼 수 있습니다.
  </p>
</template>

<style scoped>
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

h1 {
  margin: 0;
  font-size: 1.25rem;
}

.head .hint {
  margin: 0.25rem 0 0;
}

.head-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.small {
  padding: 0.4rem 0.7rem;
  font-size: 0.85rem;
  white-space: nowrap;
}

.period {
  margin: 0.75rem 0 0;
  font-size: 0.9rem;
}

.not-today {
  margin-left: 0.5rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: #fff8e1;
  color: #8a6100;
  font-size: 0.78rem;
  font-weight: 600;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.9rem;
  list-style: none;
  margin: 0.6rem 0;
  padding: 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.legend li {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.sw {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.sw.free {
  background: #dff2e1;
}

.sw.booked {
  background: #d93a33;
}

.sw.using {
  background: #f5b912;
}

.sw.past {
  background: #9ba2ad;
}

.sw.nowline {
  width: 4px;
  border-radius: 2px;
  background: #1a73e8;
}

.updated {
  margin-top: 0.6rem;
}
</style>
