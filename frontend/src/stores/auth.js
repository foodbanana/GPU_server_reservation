// 로그인 상태 보관소 (Pinia).
// 토큰은 localStorage 에 두어서 새로고침해도 로그인이 풀리지 않게 한다.

import { defineStore } from 'pinia'
import { api, getToken, setToken } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken(),
    user: null, // { id, name, email, is_admin }
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },

  actions: {
    async signup({ name, email, password, inviteCode }) {
      await api.signup({
        name,
        email,
        password,
        invite_code: inviteCode,
      })
      // 가입 후 바로 로그인까지 해 준다
      await this.login({ email, password })
    },

    async login({ email, password }) {
      const data = await api.login({ email, password })
      this.token = data.access_token
      setToken(this.token)
      await this.fetchMe()
    },

    async fetchMe() {
      if (!this.token) return null
      this.user = await api.me()
      return this.user
    },

    logout() {
      this.token = null
      this.user = null
      setToken(null)
    },
  },
})
