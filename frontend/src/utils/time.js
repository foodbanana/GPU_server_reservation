// 한국 시간(KST) 다루기.
//
// 브라우저가 어느 시간대로 설정돼 있든 상관없이 항상 한국 시간으로 계산한다.
// 서버에는 "2026-09-17T10:00:00+09:00" 처럼 +09:00 이 붙은 문자열을 보낸다.

const KST = 'Asia/Seoul'

const 부품형식 = new Intl.DateTimeFormat('en-CA', {
  timeZone: KST,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Date 객체를 한국 시간 기준 { date: 'YYYY-MM-DD', hour: 0~23, minute: 0~59 } 로 */
export function kstParts(date = new Date()) {
  const p = {}
  for (const { type, value } of 부품형식.formatToParts(date)) p[type] = value
  let hour = Number(p.hour)
  if (hour === 24) hour = 0 // 일부 환경에서 자정을 24로 주는 경우 대비
  return {
    date: `${p.year}-${p.month}-${p.day}`,
    hour,
    minute: Number(p.minute),
  }
}

/** 날짜 문자열 + 시(정시)를 서버에 보낼 ISO8601 문자열로. */
export function toIso(dateStr, hour) {
  return `${dateStr}T${String(hour).padStart(2, '0')}:00:00+09:00`
}

/** 날짜 문자열 + 시에서 시간을 더한 뒤 다시 { date, hour } 로 */
export function addHours(dateStr, hour, plusHours) {
  const t = new Date(toIso(dateStr, hour)).getTime() + plusHours * 3600 * 1000
  const { date, hour: h } = kstParts(new Date(t))
  return { date, hour: h }
}

/** 두 시각 사이가 몇 시간인지 */
export function diffHours(startDate, startHour, endDate, endHour) {
  const ms = new Date(toIso(endDate, endHour)) - new Date(toIso(startDate, startHour))
  return Math.round(ms / 3600000)
}

/** 서버가 준 ISO 문자열을 '2026-09-17 10:00' 처럼 보기 좋게 */
export function formatKst(isoString) {
  const { date, hour, minute } = kstParts(new Date(isoString))
  return `${date} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

/** 0~23 시 목록 (예약은 정시 단위이므로) */
export const HOURS = Array.from({ length: 24 }, (_, i) => i)

/** '2026-09-16' -> '화' (한국 요일 한 글자) */
const 요일형식 = new Intl.DateTimeFormat('ko-KR', { timeZone: KST, weekday: 'short' })
export function weekdayKo(dateStr) {
  // 정오를 기준으로 봐야 시간대 계산에서 하루가 밀리지 않는다
  return 요일형식.format(new Date(toIso(dateStr, 12)))
}

/** '2026-09-16' -> '9/16' (타임라인 날짜 머리글용 짧은 표기) */
export function shortDate(dateStr) {
  const [, month, day] = dateStr.split('-')
  return `${Number(month)}/${Number(day)}`
}

/** 서버가 준 ISO 문자열을 '9/16 14:00' 처럼 짧게 (툴팁용) */
export function formatKstShort(isoString) {
  const { date, hour, minute } = kstParts(new Date(isoString))
  return `${shortDate(date)} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}
