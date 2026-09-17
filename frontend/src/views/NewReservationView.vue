<script setup>
// 예약 신청 화면.
// - 주소에 gpuId 가 없으면: GPU 버튼 12개를 보여준다.
// - gpuId 가 있으면: 그 GPU의 시작·종료 날짜·시간을 고르는 폼을 보여준다.
//
// 예약 시간 길이 제한과 '14일 이내 시작' 제한은 없다 (연구실에서 협의해 쓴다).
// 화면이 미리 걸러 주는 것은 '종료가 시작보다 뒤인가'와 '이미 잡힌 예약과 겹치는가' 두 가지뿐이고,
// 진짜 판정은 언제나 서버가 한다.
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import GpuButtonGrid from '../components/GpuButtonGrid.vue'
import { api } from '../api/client'
import { HOURS, addHours, diffHours, formatKst, kstParts, toIso } from '../utils/time'

const props = defineProps({
  gpuId: { type: [String, Number], default: null },
})

const router = useRouter()

const gpus = ref([])
const 기존예약 = ref([])
const 불러오는중 = ref(true)
const 보내는중 = ref(false)
const 오류 = ref('')
const 성공 = ref('')

const 시작날짜 = ref('')
const 시작시 = ref(0)
const 종료날짜 = ref('')
const 종료시 = ref(0)

// 방금 신청에 성공한 예약의 id.
// 성공 직후에는 입력칸에 방금 예약한 시간이 그대로 남아 있는데,
// 새로고침한 예약 목록에는 그 예약이 들어 있어서 "내가 방금 만든 예약과 겹친다"는
// 엉뚱한 경고가 떴다. 그래서 이 예약 하나만 사전 검사에서 빼 둔다.
// 입력을 조금이라도 건드리거나 다시 신청하면 곧바로 검사 대상으로 되돌린다.
const 방금예약ID = ref(null)

const 선택GPU = computed(() =>
  props.gpuId ? gpus.value.find((g) => g.id === Number(props.gpuId)) ?? null : null,
)

const 예약길이 = computed(() => {
  if (!시작날짜.value || !종료날짜.value) return 0
  return diffHours(시작날짜.value, 시작시.value, 종료날짜.value, 종료시.value)
})

/** 오늘(한국 시간) — 날짜 선택 칸의 최소값. 최대값은 두지 않는다 (기간 제한 없음) */
const 오늘 = computed(() => kstParts().date)

// ---------- 불러오기 ----------

async function 초기화() {
  불러오는중.value = true
  오류.value = ''
  try {
    gpus.value = await api.gpus()
  } catch (e) {
    오류.value = e.message
  } finally {
    불러오는중.value = false
  }
}

async function 기존예약불러오기() {
  기존예약.value = []
  if (!선택GPU.value) return
  // 끝 시각을 주지 않으면 서버가 '오늘 0시 이후의 예약 전부'를 준다 (기간 제한 없음).
  try {
    기존예약.value = await api.gpuReservations(선택GPU.value.id, toIso(오늘.value, 0))
  } catch (e) {
    오류.value = e.message
  }
}

/** 시작·종료 기본값: 다음 정시부터 1시간 */
function 기본시각채우기() {
  const 지금 = kstParts()
  const 시작 = addHours(지금.date, 지금.hour, 1)
  시작날짜.value = 시작.date
  시작시.value = 시작.hour

  const 종료 = addHours(시작.date, 시작.hour, 1)
  종료날짜.value = 종료.date
  종료시.value = 종료.hour
}

초기화()

// GPU 를 고르거나 바꾸면 그 GPU의 예약 목록과 기본 시각을 다시 준비한다
watch(
  선택GPU,
  () => {
    if (!선택GPU.value) return
    성공.value = ''
    오류.value = ''
    방금예약ID.value = null
    기본시각채우기()
    기존예약불러오기()
  },
  { immediate: true },
)

// 시작·종료를 조금이라도 바꾸면 성공 메시지를 지우고,
// 방금 만든 예약도 다시 겹침 검사 대상에 넣는다.
// (같은 시간을 다시 입력하면 정상적으로 겹침 경고가 떠야 하므로)
watch([시작날짜, 시작시, 종료날짜, 종료시], () => {
  성공.value = ''
  방금예약ID.value = null
})

// ---------- 편의용 사전 검사 (진짜 판정은 서버가 한다) ----------

const 겹치는예약 = computed(() => {
  if (예약길이.value <= 0) return null
  const s = new Date(toIso(시작날짜.value, 시작시.value)).getTime()
  const e = new Date(toIso(종료날짜.value, 종료시.value)).getTime()
  return (
    기존예약.value.find((r) => {
      if (r.id === 방금예약ID.value) return false // 방금 내가 만든 예약
      const rs = new Date(r.start_at).getTime()
      const re = new Date(r.end_at).getTime()
      // 겹침: 새 시작 < 기존 종료 AND 새 종료 > 기존 시작
      return s < re && e > rs
    }) ?? null
  )
})

const 미리보기경고 = computed(() => {
  if (!시작날짜.value || !종료날짜.value) return ''
  if (예약길이.value <= 0) return '종료 시각은 시작 시각보다 뒤여야 합니다.'
  if (겹치는예약.value) {
    return `이미 예약된 시간과 겹칩니다. (${formatKst(겹치는예약.value.start_at)} ~ ${formatKst(겹치는예약.value.end_at)})`
  }
  return ''
})

/** '50시간 (2일 2시간)' 처럼 길게 잡은 예약을 알아보기 쉽게 */
const 길이설명 = computed(() => {
  const h = 예약길이.value
  if (h < 24) return ''
  const 일 = Math.floor(h / 24)
  const 나머지 = h % 24
  return 나머지 === 0 ? `(${일}일)` : `(${일}일 ${나머지}시간)`
})

// ---------- 보내기 ----------

async function 예약신청() {
  오류.value = ''
  성공.value = ''
  // 같은 시간을 한 번 더 신청하는 경우이므로, 방금 만든 예약도 다시 검사 대상으로
  방금예약ID.value = null
  보내는중.value = true
  try {
    const 결과 = await api.createReservation({
      gpu_id: 선택GPU.value.id,
      start_at: toIso(시작날짜.value, 시작시.value),
      end_at: toIso(종료날짜.value, 종료시.value),
    })
    await 기존예약불러오기()
    방금예약ID.value = 결과.id
    성공.value = `예약되었습니다. ${결과.gpu_label} / ${formatKst(결과.start_at)} ~ ${formatKst(결과.end_at)}`
  } catch (e) {
    // 서버가 보내 준 한국어 메시지를 그대로 보여 준다 (중복·규칙 위반 등)
    오류.value = e.message
  } finally {
    보내는중.value = false
  }
}

function 목록으로() {
  router.push({ name: 'reserve' })
}
</script>

<template>
  <p v-if="불러오는중" class="hint">불러오는 중…</p>

  <template v-else-if="!선택GPU">
    <h1>예약할 GPU를 고르세요</h1>
    <p v-if="오류" class="error-box">{{ 오류 }}</p>
    <GpuButtonGrid :gpus="gpus" />
  </template>

  <template v-else>
    <button class="btn-secondary back" @click="목록으로">← GPU 목록으로</button>

    <div class="card">
      <h1>{{ 선택GPU.label }}</h1>
      <p class="hint">
        {{ 선택GPU.category_label }} GPU · 예약은 정시 단위입니다 ·
        예약 길이와 기간 제한은 없습니다. 오래 쓸 때는 서로 협의해 주세요.
      </p>

      <form @submit.prevent="예약신청">
        <div class="field">
          <label>시작</label>
          <div class="datetime">
            <input v-model="시작날짜" type="date" :min="오늘" required />
            <select v-model.number="시작시">
              <option v-for="h in HOURS" :key="h" :value="h">
                {{ String(h).padStart(2, '0') }}:00
              </option>
            </select>
          </div>
        </div>

        <div class="field">
          <label>종료</label>
          <div class="datetime">
            <input v-model="종료날짜" type="date" :min="시작날짜" required />
            <select v-model.number="종료시">
              <option v-for="h in HOURS" :key="h" :value="h">
                {{ String(h).padStart(2, '0') }}:00
              </option>
            </select>
          </div>
        </div>

        <p class="length">
          예약 길이: <strong>{{ 예약길이 }}시간</strong>
          <span v-if="길이설명" class="days">{{ 길이설명 }}</span>
        </p>

        <p v-if="미리보기경고" class="warn-box">{{ 미리보기경고 }}</p>
        <p v-if="오류" class="error-box">{{ 오류 }}</p>
        <p v-if="성공" class="success-box">{{ 성공 }}</p>

        <button class="btn-primary wide" type="submit" :disabled="보내는중">
          {{ 보내는중 ? '신청 중…' : '예약 신청' }}
        </button>
      </form>
    </div>

    <div class="card existing">
      <h2>이 GPU에 이미 잡혀 있는 예약</h2>
      <p v-if="기존예약.length === 0" class="hint">앞으로 잡힌 예약이 없습니다.</p>
      <ul v-else>
        <li v-for="r in 기존예약" :key="r.id">
          <span class="time">{{ formatKst(r.start_at) }} ~ {{ formatKst(r.end_at) }}</span>
          <span class="who">{{ r.user_name }}</span>
        </li>
      </ul>
    </div>
  </template>
</template>

<style scoped>
h1 {
  margin-top: 0;
  font-size: 1.25rem;
}

h2 {
  margin-top: 0;
  font-size: 1rem;
}

.back {
  margin-bottom: 0.9rem;
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
  margin: 0.75rem 0 0;
}

.days {
  margin-left: 0.35rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.warn-box {
  background: #fff8e1;
  border: 1px solid #f0d58c;
  color: #8a6100;
  border-radius: 6px;
  padding: 0.75rem 0.9rem;
  margin: 0.75rem 0;
  line-height: 1.5;
}

.wide {
  width: 100%;
  margin-top: 0.5rem;
}

.existing {
  margin-top: 1rem;
}

.existing ul {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}

.existing li {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.5rem 0;
  border-top: 1px solid var(--gray-line);
  font-size: 0.9rem;
}

.existing .who {
  color: var(--muted);
}
</style>
