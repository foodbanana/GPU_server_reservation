import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api/client'
import './style.css'

// 토큰이 만료되면 어디서든 로그인 화면으로 보내진다
setUnauthorizedHandler(() => router.push({ name: 'login' }))

createApp(App).use(createPinia()).use(router).mount('#app')
