// 서버를 부르는 공통 함수.
//
// - 로그인 토큰(JWT)을 자동으로 붙인다.
// - 서버가 준 한국어 오류 메시지({"detail": "..."})를 그대로 Error 로 던진다.
// - 401(로그인 만료)이면 토큰을 지우고 로그인 화면으로 보낸다.

const TOKEN_KEY = 'gpu-reserve-token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

// router 를 직접 import 하면 서로 물고 물리는 문제가 생겨서, main.js 에서 넣어 준다.
let 로그인화면으로 = () => {}
export function setUnauthorizedHandler(fn) {
  로그인화면으로 = fn
}

export async function request(path, { method = 'GET', body, params, auth = true } = {}) {
  let url = path
  if (params) {
    const q = new URLSearchParams(params).toString()
    if (q) url += `?${q}`
  }

  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (auth && token) headers['Authorization'] = `Bearer ${token}`

  let response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new Error('서버에 연결할 수 없습니다. 백엔드가 켜져 있는지 확인해 주세요.')
  }

  if (response.status === 401 && auth) {
    setToken(null)
    로그인화면으로()
    throw new Error('로그인이 만료되었습니다. 다시 로그인해 주세요.')
  }

  if (response.status === 204) return null

  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    throw new Error(오류메시지(data, response.status))
  }
  return data
}

/** FastAPI 가 주는 오류를 사람이 읽을 수 있는 한 줄로 바꾼다. */
function 오류메시지(data, status) {
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  // 입력 형식이 틀렸을 때 FastAPI 는 detail 에 목록을 담아 준다
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d.msg ?? '입력값이 올바르지 않습니다.').join('\n')
  }
  return `요청이 실패했습니다. (오류 코드 ${status})`
}

// 화면에서 쓰는 서버 호출 모음
export const api = {
  signup: (body) => request('/api/auth/signup', { method: 'POST', body, auth: false }),
  login: (body) => request('/api/auth/login', { method: 'POST', body, auth: false }),
  me: () => request('/api/auth/me'),
  config: () => request('/api/config', { auth: false }),
  gpus: () => request('/api/gpus'),
  // end 를 주지 않으면 start 이후의 예약을 기간 제한 없이 모두 받는다
  gpuReservations: (gpuId, start, end) =>
    request(`/api/gpus/${gpuId}/reservations`, {
      params: end ? { start, end } : { start },
    }),
  // 타임라인 화면용: 기간과 겹치는 모든 예약 (예약자 이름 포함)
  reservations: (start, end) => request('/api/reservations', { params: { start, end } }),
  createReservation: (body) => request('/api/reservations', { method: 'POST', body }),

  // 내 예약 목록 (취소한 것 포함)
  myReservations: () => request('/api/reservations/me'),
  // 시작 전인 예약 취소
  cancelReservation: (id) => request(`/api/reservations/${id}`, { method: 'DELETE' }),
  // 사용 중인 예약 조기 종료 (종료 시각을 지금 정시로 당김)
  endReservationNow: (id) =>
    request(`/api/reservations/${id}/end-now`, { method: 'POST' }),

  // ----- 관리자 전용 (관리자가 아니면 서버가 403으로 막는다) -----
  adminReservations: (params) => request('/api/admin/reservations', { params }),
  adminUpdateReservation: (id, body) =>
    request(`/api/admin/reservations/${id}`, { method: 'PATCH', body }),
  adminDeleteReservation: (id) =>
    request(`/api/admin/reservations/${id}`, { method: 'DELETE' }),
  // 가입자 목록. 비밀번호 해시는 서버가 아예 내려주지 않는다.
  adminUsers: () => request('/api/admin/users'),
  // 관리자 권한 주기/뺏기. 대상은 user_id 또는 email 중 하나만 준다.
  // 최고 관리자 해제·본인 해제·마지막 관리자 해제는 서버가 400으로 막는다.
  adminSetUserRole: (userId, isAdmin) =>
    request('/api/admin/users/role', {
      method: 'PATCH',
      body: { user_id: userId, is_admin: isAdmin },
    }),
}
