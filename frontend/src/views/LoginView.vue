<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandHeader from '../components/BrandHeader.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const 오류 = ref('')
const 보내는중 = ref(false)

async function 로그인() {
  오류.value = ''
  보내는중.value = true
  try {
    await auth.login({ email: email.value.trim(), password: password.value })
    router.push(route.query.next || { name: 'timeline' })
  } catch (e) {
    오류.value = e.message
  } finally {
    보내는중.value = false
  }
}
</script>

<template>
  <BrandHeader />

  <div class="card">
    <h2>로그인</h2>

    <form @submit.prevent="로그인">
      <div class="field">
        <label for="email">이메일</label>
        <input id="email" v-model="email" type="email" required autocomplete="username" />
      </div>

      <div class="field">
        <label for="password">비밀번호</label>
        <input
          id="password"
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
        />
      </div>

      <p v-if="오류" class="error-box">{{ 오류 }}</p>

      <button class="btn-primary wide" type="submit" :disabled="보내는중">
        {{ 보내는중 ? '로그인 중…' : '로그인' }}
      </button>
    </form>

    <p class="hint">
      아직 계정이 없나요?
      <RouterLink to="/signup">회원가입</RouterLink>
    </p>
  </div>
</template>

<style scoped>
h2 {
  margin-top: 0;
  font-size: 1.15rem;
}

.wide {
  width: 100%;
}
</style>
