import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 개발할 때만 쓰는 설정이다.
//
// 운영(배포)에서는 `npm run build` 결과를 FastAPI 가 함께 내보내므로
// 포트 하나(8000)로 화면과 API가 모두 동작한다. 아래 proxy 는 쓰이지 않는다.
//
// 개발 중에는 화면이 5173, 백엔드가 **8001** 포트로 따로 돈다.
// 8000 은 운영 서버(systemd)가 계속 쓰고 있으므로 개발은 8001 을 쓴다.
// 브라우저가 /api/... 를 부르면 vite 가 8001 번으로 대신 넘겨준다(proxy).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true, // 같은 네트워크의 휴대폰에서도 접속할 수 있게
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
