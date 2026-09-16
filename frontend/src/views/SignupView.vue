<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const name = ref('')
const email = ref('')
const password = ref('')
const inviteCode = ref('')
const 오류 = ref('')
// 가입 코드 오류는 일반 오류 상자 대신 입력칸 바로 아래에 보여 준다
const 가입코드오류 = ref('')
const 보내는중 = ref(false)

// 코드를 다시 입력하기 시작하면 오류 표시를 지운다
watch(inviteCode, () => {
  가입코드오류.value = ''
})

async function 가입() {
  오류.value = ''
  가입코드오류.value = ''

  // 편의용 사전 검사. 진짜 판정은 언제나 서버가 한다.
  if (password.value.length === 0) {
    오류.value = '비밀번호를 입력해 주세요.'
    return
  }
  if (inviteCode.value.trim().length === 0) {
    가입코드오류.value = '연구실 가입 코드를 입력해 주세요.'
    return
  }

  보내는중.value = true
  try {
    await auth.signup({
      name: name.value.trim(),
      email: email.value.trim(),
      password: password.value,
      inviteCode: inviteCode.value.trim(),
    })
    router.push({ name: 'reserve' })
  } catch (e) {
    // 가입 코드 문제면 입력칸 아래에, 그 밖의 문제면 일반 오류 상자에 보여 준다.
    // (서버가 보내 준 메시지를 그대로 쓰며, 실제 가입 코드 값은 어디에도 담기지 않는다)
    if (e.message.includes('가입 코드')) {
      가입코드오류.value = e.message
    } else {
      오류.value = e.message
    }
  } finally {
    보내는중.value = false
  }
}
</script>

<template>
  <div class="card">
    <h1>회원가입</h1>

    <form @submit.prevent="가입">
      <div class="field">
        <label for="name">이름</label>
        <input id="name" v-model="name" type="text" required maxlength="50" />
        <p class="hint">예약 화면에 표시될 이름입니다.</p>
      </div>

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
          autocomplete="new-password"
        />
      </div>

      <div class="field">
        <label for="invite">연구실 가입 코드</label>
        <input
          id="invite"
          v-model="inviteCode"
          type="text"
          required
          :class="{ invalid: 가입코드오류 }"
          :aria-invalid="Boolean(가입코드오류)"
          aria-describedby="invite-help"
        />
        <p v-if="가입코드오류" id="invite-help" class="field-error" role="alert">
          {{ 가입코드오류 }}
        </p>
        <p v-else id="invite-help" class="hint">연구실에서 받은 코드를 입력하세요.</p>
      </div>

      <p v-if="오류" class="error-box">{{ 오류 }}</p>

      <button class="btn-primary wide" type="submit" :disabled="보내는중">
        {{ 보내는중 ? '가입 중…' : '가입하고 시작하기' }}
      </button>
    </form>

    <p class="hint">
      이미 계정이 있나요?
      <RouterLink to="/login">로그인</RouterLink>
    </p>
  </div>
</template>

<style scoped>
h1 {
  margin-top: 0;
  font-size: 1.35rem;
}

.wide {
  width: 100%;
}

/* 가입 코드 입력칸 바로 아래에 붙는 오류 문구 */
.field-error {
  color: var(--red);
  font-size: 0.875rem;
  margin: 0.35rem 0 0;
  line-height: 1.4;
}

input.invalid {
  border-color: var(--red);
}
</style>
