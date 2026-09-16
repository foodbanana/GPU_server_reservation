<script setup>
// 메인 화면: 2주치 예약 현황 타임라인 (SPEC 8장 2번).
//
// 서버에서 GPU 목록과 '오늘 0시 ~ 14일 후' 기간의 예약을 받아 TimelineGrid 에 넘긴다.
// 1분마다 현재 시각과 예약 목록을 새로 받아서 세로선과 색이 저절로 맞춰지게 한다.

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import TimelineGrid from '../components/TimelineGrid.vue'
import { api } from '../api/client'
import { addHours, formatKst, kstParts, toIso } from '../utils/time'

const 기본일수 = 14

const gpus = ref([])
const 예약 = ref([])
const 일수 = ref(기본일수)
const 지금 = ref(new Date())
const 불러오는중 = ref(true)
const 오류 = ref('')
const 마지막갱신 = ref(null)

const grid = ref(null)

let 타이머 = null

/** 조회 범위: 오늘 0시 ~ 일수 뒤 0시 */
const 조회범위 = computed(() => {
  const 오늘 = kstParts(지금.value).date
  return {
    start: toIso(오늘, 0),
    end: toIso(addHours(오늘, 0, 일수.value * 24).date, 0),
  }
})

async function 불러오기({ 처음 = false } = {}) {
  if (처음) 불러오는중.value = true
  지금.value = new Date()
  try {
    // 설정값(booking_horizon_days)이 14가 아니면 그 값에 맞춰 표를 그린다
    if (처음) {
      const 설정 = await api.config()
      일수.value = 설정?.booking_horizon_days ?? 기본일수
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

onMounted(() => {
  불러오기({ 처음: true })
  // 1분마다 현재 시각 세로선과 예약 목록을 갱신한다
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
        오늘 0시부터 {{ 일수 }}일 뒤까지 · 1칸 = 1시간 · GPU 줄을 누르면 그 GPU 예약 화면으로 갑니다.
      </p>
    </div>
    <div class="head-actions">
      <button class="btn-secondary small" @click="grid?.지금으로스크롤()">지금으로</button>
      <button class="btn-secondary small" :disabled="불러오는중" @click="불러오기()">
        새로고침
      </button>
    </div>
  </div>

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
}

.small {
  padding: 0.4rem 0.7rem;
  font-size: 0.85rem;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.9rem;
  list-style: none;
  margin: 0.75rem 0;
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
