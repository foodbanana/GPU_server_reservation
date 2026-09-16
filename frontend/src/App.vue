<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()

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
    <span class="brand">연구실 GPU 예약</span>
    <div v-if="auth.isLoggedIn" class="topbar-right">
      <span class="who">{{ auth.user?.name }} 님</span>
      <button class="logout" @click="로그아웃">로그아웃</button>
    </div>
  </header>

  <main class="page">
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

.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 1.25rem 1rem 3rem;
}
</style>
