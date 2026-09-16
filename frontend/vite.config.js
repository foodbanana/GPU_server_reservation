import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 개발 중에는 프론트엔드가 5173 포트, 백엔드가 8000 포트로 따로 돈다.
// 브라우저가 /api/... 를 부르면 vite 가 8000 번으로 대신 넘겨준다(proxy).
// 덕분에 프론트엔드 코드에는 주소를 적을 필요가 없다.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true, // 같은 네트워크의 휴대폰에서도 접속할 수 있게
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
