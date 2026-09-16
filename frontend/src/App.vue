<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// 타임라인처럼 넓은 화면은 본문 폭 제한을 푼다 (router/index.js 의 meta.wide)
const 넓은화면 = computed(() => Boolean(route.meta.wide))

onMounted(async () => {
  // 새로고침했을 때 토큰만 있고 사용자 정보가 없으면 다시 받아온다
  if (auth.isLoggedIn && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
    }
  }
})

function 로그아웃() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="topbar">
    <RouterLink class="brand" :to="{ name: 'timeline' }">연구실 GPU 예약</RouterLink>
    <div v-if="auth.isLoggedIn" class="topbar-right">
      <span class="who">{{ auth.user?.name }} 님</span>
      <button class="logout" @click="로그아웃">로그아웃</button>
    </div>
  </header>

  <nav v-if="auth.isLoggedIn" class="menu">
    <RouterLink class="home" :to="{ name: 'timeline' }">예약 현황</RouterLink>
    <RouterLink :to="{ name: 'reserve' }">예약 신청</RouterLink>
  </nav>

  <main class="page" :class="{ wide: 넓은화면 }">
    <RouterView />
  </main>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  background: #fff;
  border-bottom: 1px solid var(--gray-line);
}

.brand {
  font-weight: 700;
  color: inherit;
  text-decoration: none;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.who {
  font-size: 0.9rem;
  color: var(--muted);
}

.logout {
  background: none;
  border: 1px solid var(--gray-line);
  border-radius: 6px;
  padding: 0.35rem 0.7rem;
  font-size: 0.85rem;
}

/* 화면 이동 메뉴 */
.menu {
  display: flex;
  gap: 0.25rem;
  padding: 0 0.5rem;
  background: #fff;
  border-bottom: 1px solid var(--gray-line);
  overflow-x: auto;
}

.menu a {
  padding: 0.6rem 0.85rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--muted);
  text-decoration: none;
  border-bottom: 3px solid transparent;
  white-space: nowrap;
}

 /* '예약 현황'(/)은 정확히 그 주소일 때만, '예약 신청'은 /reserve/3 같은 하위 주소에서도 표시 */
.menu a.router-link-exact-active,
.menu a.router-link-active:not(.home) {
  color: #1a73e8;
  border-bottom-color: #1a73e8;
}

.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 1.25rem 1rem 3rem;
}

.page.wide {
  max-width: 1400px;
}

@media (max-width: 720px) {
  .page {
    padding: 1rem 0.6rem 2.5rem;
  }
}
</style>
