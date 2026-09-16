// 화면 주소 연결. 로그인하지 않았으면 로그인 화면으로 보낸다.

import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import NewReservationView from '../views/NewReservationView.vue'
import { getToken } from '../api/client'

const routes = [
  // Phase 3에서 메인 화면(타임라인)이 생기면 '/' 는 그쪽으로 바뀐다.
  { path: '/', redirect: '/reserve' },
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/signup', name: 'signup', component: SignupView, meta: { public: true } },
  {
    path: '/reserve',
    name: 'reserve',
    component: NewReservationView,
  },
  {
    // GPU 버튼을 누르면 이 주소로 온다. 같은 화면이 예약 신청 폼으로 바뀐다.
    path: '/reserve/:gpuId',
    name: 'reserve-gpu',
    component: NewReservationView,
    props: true,
  },
  { path: '/:pathMatch(.*)*', redirect: '/reserve' },
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
    return { name: 'reserve' }
  }
  return true
})

export default router
