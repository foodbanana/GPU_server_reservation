<script setup>
// 예약 현황 표 (SPEC 8장 2번).
//
// 가로: 오늘 0시부터 days 일(기본 14일) 동안을 1시간 = 1칸으로 그린다.
// 세로: GPU 12행을 단주기 그룹 / 장주기 그룹으로 나눈다.
//
// 그리는 방법
//  - 칸 하나하나를 태그로 만들면 4000개가 넘으므로, 각 행의 바탕을
//    '초록색 + 1시간마다 세로줄' 무늬(CSS 배경)로 그린다. = 예약 가능
//  - 예약은 그 위에 막대(블록) 하나로 올린다. 미래=빨강, 진행 중=노랑
//  - 지나간 시간은 행 왼쪽 끝부터 현재 시각까지를 회색 반투명으로 덮는다.
//  - 칸 너비(--hour-w)는 CSS 에만 있고, 블록 위치는 calc() 로 계산하므로
//    휴대폰에서 칸이 좁아져도 자동으로 맞는다.

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { addHours, formatKstShort, kstParts, shortDate, toIso, weekdayKo } from '../utils/time'

const props = defineProps({
  gpus: { type: Array, required: true },
  reservations: { type: Array, required: true },
  now: { type: Date, required: true },
  days: { type: Number, default: 14 },
})

const router = useRouter()

const 스크롤러 = ref(null)
const 자동스크롤함 = ref(false)
const 툴팁 = ref(null) // { x, y, gpu, block }

// ---------- 시간 축 ----------

/** 표의 왼쪽 끝 = 오늘 0시 (한국 시간) */
const 시작날짜 = computed(() => kstParts(props.now).date)
const 시작시각 = computed(() => new Date(toIso(시작날짜.value, 0)).getTime())
const 총시간 = computed(() => props.days * 24)
const 끝시각 = computed(() => 시작시각.value + 총시간.value * 3600000)

/** 시간 축 전체 너비. 칸 너비는 CSS(--hour-w)가 정하므로 calc 로 넘긴다 */
const 트랙너비 = computed(() => `calc(var(--hour-w) * ${총시간.value})`)

/** 현재 시각이 표의 왼쪽 끝에서 몇 칸(시간) 떨어져 있는가. 소수점 포함 */
const 지금위치 = computed(() => (props.now.getTime() - 시작시각.value) / 3600000)

/** 날짜 머리글: [{ date, label, 요일, 오늘인가 }] */
const 날짜목록 = computed(() => {
  const 오늘 = 시작날짜.value
  return Array.from({ length: props.days }, (_, i) => {
    const date = addHours(오늘, 0, i * 24).date
    return { date, label: shortDate(date), weekday: weekdayKo(date), today: i === 0 }
  })
})

/** 시간 머리글: 0,1,2,...,23,0,1,... (3시간마다만 숫자를 보여 준다) */
const 시간목록 = computed(() =>
  Array.from({ length: 총시간.value }, (_, i) => {
    const hour = i % 24
    return { key: i, hour, tick: hour % 3 === 0, tick6: hour % 6 === 0 }
  }),
)

// ---------- 행과 예약 블록 ----------

function 블록만들기(gpuId) {
  const now = props.now.getTime()
  const blocks = []
  for (const r of props.reservations) {
    if (r.gpu_id !== gpuId) continue
    const s = new Date(r.start_at).getTime()
    const e = new Date(r.end_at).getTime()
    // 표 밖으로 나가는 부분은 잘라서 그린다
    const left = Math.max(0, Math.round((s - 시작시각.value) / 3600000))
    const right = Math.min(총시간.value, Math.round((e - 시작시각.value) / 3600000))
    if (right <= left) continue

    let state = 'future' // 예약됨 = 빨강
    if (e <= now) state = 'past' // 이미 끝남 (회색 덮개가 덮는다)
    else if (s <= now) state = 'now' // 사용 중 = 노랑

    blocks.push({
      id: r.id,
      left,
      span: right - left,
      state,
      name: r.user_name,
      start: r.start_at,
      end: r.end_at,
      cutLeft: s < 시작시각.value, // 표 왼쪽 밖에서 시작한 예약
      cutRight: e > 끝시각.value, // 표 오른쪽 밖까지 이어지는 예약
    })
  }
  return blocks.sort((a, b) => a.left - b.left)
}

function 그룹만들기(category, title, hint) {
  const gpus = props.gpus.filter((g) => g.category === category)
  return {
    category,
    title,
    hint,
    rows: gpus.map((gpu) => ({ gpu, blocks: 블록만들기(gpu.id) })),
  }
}

const 그룹목록 = computed(() => [
  그룹만들기('short', '단주기 GPU', '짧게 쓰는 GPU'),
  그룹만들기('long', '장주기 GPU', '길게 쓰는 GPU'),
])

// ---------- 클릭·툴팁 ----------

function 예약화면으로(gpu) {
  router.push({ name: 'reserve-gpu', params: { gpuId: gpu.id } })
}

function 툴팁열기(event, gpu, block) {
  const rect = event.currentTarget.getBoundingClientRect()
  // 화면(viewport) 기준 위치. 표 안에 넣으면 잘려서 안 보이므로 화면에 띄운다.
  const 여백 = 120
  const x = Math.min(Math.max(rect.left + rect.width / 2, 여백), window.innerWidth - 여백)
  툴팁.value = { x, y: rect.top, gpu, block }
}

function 툴팁닫기() {
  툴팁.value = null
}

// ---------- 현재 시각으로 자동 스크롤 ----------

/** CSS 에 적힌 칸 너비(--hour-w)를 px 숫자로 읽어 온다 */
function css값(name, 기본값) {
  const el = 스크롤러.value
  if (!el) return 기본값
  const raw = getComputedStyle(el).getPropertyValue(name)
  const n = Number.parseFloat(raw)
  return Number.isFinite(n) ? n : 기본값
}

function 지금으로스크롤() {
  const el = 스크롤러.value
  if (!el) return
  const 칸너비 = css값('--hour-w', 30)
  const 이름칸 = css값('--label-w', 138)
  // 현재 시각이 '시간 부분'의 왼쪽에서 1/4 지점에 오도록 (조금 전 상황도 같이 보이게).
  // 이름칸 너비를 빼 주지 않으면 휴대폰에서 세로선이 이름칸 뒤에 숨는다.
  const 보이는폭 = Math.max(el.clientWidth - 이름칸, 120)
  const x = 칸너비 * 지금위치.value - 보이는폭 * 0.25
  el.scrollLeft = Math.max(0, x)
}

// GPU 목록은 서버에서 늦게 오므로, 행이 처음 그려진 뒤에 한 번 스크롤한다
watch(
  () => props.gpus.length,
  async (n) => {
    if (n > 0 && !자동스크롤함.value) {
      자동스크롤함.value = true
      await nextTick()
      지금으로스크롤()
    }
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('resize', 툴팁닫기))
onBeforeUnmount(() => window.removeEventListener('resize', 툴팁닫기))

defineExpose({ 지금으로스크롤 })
</script>

<template>
  <div class="timeline">
    <div ref="스크롤러" class="tl-scroll" @scroll="툴팁닫기">
      <!-- 머리글: 날짜 줄 + 시간 줄 -->
      <div class="tl-head">
        <div class="tl-corner">GPU</div>
        <div class="tl-headtracks">
          <div class="tl-days">
            <div
              v-for="d in 날짜목록"
              :key="d.date"
              class="tl-day"
              :class="{ today: d.today }"
            >
              <span class="d-label">
                <span class="d-num">{{ d.label }}</span>
                <span class="d-wd">({{ d.weekday }})</span>
              </span>
            </div>
          </div>
          <div class="tl-hours">
            <div
              v-for="h in 시간목록"
              :key="h.key"
              class="tl-hour"
              :class="{ tick: h.tick, tick6: h.tick6, dayline: h.hour === 0 }"
            >
              <span>{{ h.hour }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 본문: 그룹별 GPU 행 -->
      <div class="tl-body">
        <template v-for="group in 그룹목록" :key="group.category">
          <div class="tl-group">
            <span class="tl-group-label" :class="group.category">
              {{ group.title }}
              <em>{{ group.hint }}</em>
            </span>
          </div>

          <div
            v-for="row in group.rows"
            :key="row.gpu.id"
            class="tl-row"
            role="button"
            tabindex="0"
            :title="`${row.gpu.label} 예약하기`"
            @click="예약화면으로(row.gpu)"
            @keydown.enter="예약화면으로(row.gpu)"
          >
            <div class="tl-label" :class="group.category">
              <span class="l-name">서버{{ row.gpu.server_no }} · GPU{{ row.gpu.gpu_index }}</span>
              <span class="l-model">{{ row.gpu.model }}</span>
            </div>

            <div class="tl-track" :style="{ width: 트랙너비 }">
              <!-- 예약 막대 -->
              <div
                v-for="b in row.blocks"
                :key="b.id"
                class="tl-block"
                :class="[b.state, { 'cut-left': b.cutLeft, 'cut-right': b.cutRight }]"
                :style="{
                  left: `calc(var(--hour-w) * ${b.left} + 1px)`,
                  width: `calc(var(--hour-w) * ${b.span} - 2px)`,
                }"
                @click.stop="툴팁열기($event, row.gpu, b)"
                @mouseenter="툴팁열기($event, row.gpu, b)"
                @mouseleave="툴팁닫기"
              >
                <span class="b-name">{{ b.name }}</span>
              </div>

              <!-- 지나간 시간 덮개 (회색) -->
              <div
                class="tl-past"
                :style="{ width: `calc(var(--hour-w) * ${Math.max(지금위치, 0)})` }"
              />
            </div>
          </div>
        </template>

        <!-- 현재 시각 세로선 -->
        <div
          class="tl-nowline"
          :style="{ left: `calc(var(--label-w) + var(--hour-w) * ${지금위치})` }"
        >
          <span class="now-dot" />
        </div>
      </div>
    </div>

    <!-- 예약 자세히 보기: PC 는 마우스를 올리면, 휴대폰은 탭하면 뜬다 -->
    <div
      v-if="툴팁"
      class="tl-tip"
      :style="{ left: `${툴팁.x}px`, top: `${툴팁.y}px` }"
      @click="툴팁닫기"
    >
      <strong>{{ 툴팁.block.name }}</strong>
      <span class="t-gpu">{{ 툴팁.gpu.label }}</span>
      <span class="t-time">
        {{ formatKstShort(툴팁.block.start) }} ~ {{ formatKstShort(툴팁.block.end) }}
      </span>
      <span class="t-close">닫으려면 탭</span>
    </div>
  </div>
</template>

<style scoped>
.timeline {
  /* 칸 너비·이름칸 너비는 여기서만 정한다 (JS 는 이 값을 읽어서 스크롤한다) */
  --hour-w: 30px;
  --label-w: 138px;
  --row-h: 38px;
  --free: #dff2e1; /* 예약 가능 = 초록 */
  --line-hour: #cfe3d2;
  --line-day: #8fb894;
  position: relative;
}

/* 가로 스크롤은 이 상자 안에서만 일어난다 → 페이지 전체는 넘치지 않는다 */
.tl-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  background: #fff;
  border: 1px solid var(--gray-line);
  border-radius: 10px;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
}

/* ---------- 머리글 ---------- */
.tl-head {
  display: flex;
  width: max-content;
  position: relative;
  z-index: 6;
  background: #fff;
  border-bottom: 1px solid var(--gray-line);
}

.tl-corner {
  position: sticky;
  left: 0;
  z-index: 7;
  flex: 0 0 var(--label-w);
  display: flex;
  align-items: flex-end;
  padding: 0 0.5rem 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--muted);
  background: #fff;
  border-right: 2px solid var(--gray-line);
}

.tl-headtracks {
  display: flex;
  flex-direction: column;
}

.tl-days,
.tl-hours {
  display: flex;
}

.tl-day {
  flex: 0 0 calc(var(--hour-w) * 24);
  display: flex;
  align-items: center;
  height: 26px;
  font-size: 0.8rem;
  font-weight: 700;
  /* 날짜가 바뀌는 자리를 굵은 선으로 눈에 띄게 */
  border-left: 2px solid var(--line-day);
  background: #f7faf7;
  white-space: nowrap;
}

/* 날짜 글씨는 그 날짜 칸이 화면에 걸쳐 있는 동안 왼쪽에 붙어서 계속 보인다 */
.d-label {
  position: sticky;
  left: calc(var(--label-w) + 0.35rem);
  display: flex;
  gap: 0.25rem;
  padding-right: 0.35rem;
}

.tl-day.today {
  background: #fff4d6;
  color: #8a6100;
}

.d-wd {
  font-weight: 500;
  color: var(--muted);
}

.tl-day.today .d-wd {
  color: #8a6100;
}

.tl-hour {
  flex: 0 0 var(--hour-w);
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  color: var(--muted);
  border-left: 1px solid #eef1f4;
}

.tl-hour.dayline {
  border-left: 2px solid var(--line-day);
}

.tl-hour span {
  display: none;
}

.tl-hour.tick span {
  display: inline;
}

/* ---------- 본문 ---------- */
.tl-body {
  position: relative;
  width: max-content;
}

.tl-group {
  display: flex;
  height: 24px;
  background: #f2f4f7;
  border-bottom: 1px solid var(--gray-line);
}

.tl-group-label {
  position: sticky;
  left: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0 0.5rem;
  font-size: 0.75rem;
  font-weight: 700;
  background: #f2f4f7;
  border-left: 4px solid #1a73e8;
}

.tl-group-label.long {
  border-left-color: #6a3fb5;
}

.tl-group-label em {
  font-style: normal;
  font-weight: 400;
  color: var(--muted);
}

.tl-row {
  display: flex;
  height: var(--row-h);
  border-bottom: 1px solid var(--gray-line);
  cursor: pointer;
}

.tl-row:last-child {
  border-bottom: none;
}

.tl-label {
  position: sticky;
  left: 0;
  z-index: 5;
  flex: 0 0 var(--label-w);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 0.4rem;
  background: #fff;
  border-right: 2px solid var(--gray-line);
  border-left: 4px solid #1a73e8;
  overflow: hidden;
}

.tl-label.long {
  border-left-color: #6a3fb5;
}

.tl-row:hover .tl-label {
  background: #f0f4fa;
}

.l-name {
  font-size: 0.78rem;
  font-weight: 700;
  white-space: nowrap;
}

.l-model {
  font-size: 0.7rem;
  color: var(--muted);
  white-space: nowrap;
}

/* 행 바탕 = 예약 가능(초록) + 1시간마다 세로줄 + 하루마다 굵은 줄 */
.tl-track {
  position: relative;
  flex: none;
  background-color: var(--free);
  background-image: repeating-linear-gradient(
      to right,
      var(--line-day) 0 2px,
      transparent 2px calc(var(--hour-w) * 24)
    ),
    repeating-linear-gradient(
      to right,
      var(--line-hour) 0 1px,
      transparent 1px var(--hour-w)
    );
}

.tl-block {
  position: absolute;
  top: 3px;
  bottom: 3px;
  z-index: 1;
  display: flex;
  align-items: center;
  border-radius: 4px;
  padding: 0 0.3rem;
  font-size: 0.72rem;
  font-weight: 700;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
}

/* 예약됨 = 빨강 */
.tl-block.future,
.tl-block.past {
  background: #d93a33;
}

/* 사용 중 = 노랑 */
.tl-block.now {
  background: #f5b912;
  color: #4a3600;
}

/* 표 밖에서 이어지는 예약은 그 쪽 모서리를 각지게 해서 '계속됨'을 알린다 */
.tl-block.cut-left {
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}

.tl-block.cut-right {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.b-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 지나간 시간 = 회색으로 덮는다 */
.tl-past {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 2;
  background: rgba(150, 157, 168, 0.55);
  pointer-events: none;
}

/* 현재 시각 세로선 */
.tl-nowline {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 3;
  width: 2px;
  background: #1a73e8;
  pointer-events: none;
}

.now-dot {
  position: absolute;
  top: -4px;
  left: -4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #1a73e8;
}

/* ---------- 예약 자세히 보기 ---------- */
.tl-tip {
  position: fixed;
  z-index: 50;
  transform: translate(-50%, -110%);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 190px;
  max-width: 240px;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  background: rgba(24, 28, 35, 0.95);
  color: #fff;
  font-size: 0.78rem;
  line-height: 1.45;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
}

.tl-tip .t-gpu,
.tl-tip .t-time {
  color: #dfe4ec;
}

.tl-tip .t-close {
  margin-top: 0.15rem;
  font-size: 0.68rem;
  color: #9aa3b2;
}

/* ---------- 휴대폰 ---------- */
@media (max-width: 720px) {
  .timeline {
    --hour-w: 22px;
    --label-w: 92px;
    --row-h: 42px;
  }

  .tl-hour.tick:not(.tick6) span {
    display: none;
  }

  .l-name {
    font-size: 0.72rem;
  }

  .l-model {
    font-size: 0.65rem;
  }

  .tl-tip .t-close {
    display: block;
  }
}

@media (hover: hover) {
  /* 마우스가 있는 PC 에서는 안내 문구가 필요 없다 */
  .tl-tip .t-close {
    display: none;
  }
}
</style>
