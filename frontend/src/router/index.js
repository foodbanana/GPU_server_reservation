// 화면 주소 연결. 로그인하지 않았으면 로그인 화면으로 보낸다.

import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import NewReservationView from '../views/NewReservationView.vue'
import TimelineView from '../views/TimelineView.vue'
import { getToken } from '../api/client'

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
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const 로그인함 = Boolean(getToken())
  if (!to.meta.public && !로그인함) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.public && 로그인함) {
    return { name: 'timeline' }
  }
  return true
})

export default router
