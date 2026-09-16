// 화면 주소 연결. 로그인하지 않았으면 로그인 화면으로 보낸다.

import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import NewReservationView from '../views/NewReservationView.vue'
import TimelineView from '../views/TimelineView.vue'
import MyReservationsView from '../views/MyReservationsView.vue'
import AdminView from '../views/AdminView.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    // 메인 화면 = 2주 예약 현황 타임라인 (Phase 3)
    path: '/',
    name: 'timeline',
    component: TimelineView,
    // 타임라인은 표가 넓어서 본문 폭 제한을 풀어 준다 (App.vue 에서 사용)
    meta: { wide: true },
  },
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/signup', name: 'signup', component: SignupView, meta: { public: true } },
  {
    path: '/reserve',
    name: 'reserve',
    component: NewReservationView,
  },
  {
    // GPU 버튼(또는 타임라인의 GPU 줄)을 누르면 이 주소로 온다.
    path: '/reserve/:gpuId',
    name: 'reserve-gpu',
    component: NewReservationView,
    props: true,
  },
  {
    // 내 예약 목록 (Phase 4)
    path: '/my',
    name: 'my-reservations',
    component: MyReservationsView,
  },
  {
    // 관리자 화면 (Phase 4). meta.admin 이 붙은 주소는 아래 검사에서 막는다.
    path: '/admin',
    name: 'admin',
    component: AdminView,
    meta: { admin: true, wide: true },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.public && auth.isLoggedIn) {
    return { name: 'timeline' }
  }

  // 새로고침 직후에는 토큰만 있고 내 정보(관리자 여부)가 없다. 먼저 받아온다.
  if (auth.isLoggedIn && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { name: 'login', query: { next: to.fullPath } }
    }
  }

  // 관리자 전용 화면: 주소를 직접 입력해도 들어갈 수 없다.
  // (화면을 막는 것은 편의일 뿐이고, 진짜 차단은 서버가 403으로 한다)
  if (to.meta.admin && !auth.user?.is_admin) {
    return { name: 'timeline' }
  }

  return true
})

export default router
