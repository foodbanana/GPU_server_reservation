<script setup>
// 로그인·회원가입 화면 맨 위에 넣는 로고와 제목.
//
// 그림 파일은 frontend/public/images/ 에 있다. public 폴더에 둔 파일은
// 빌드할 때 그대로 복사되므로 주소를 '/images/...' 로 바로 쓰면 된다.
// (원본은 저장소의 picture/ 폴더에 그대로 남아 있다)
</script>

<template>
  <header class="brand">
    <img
      class="logo"
      src="/images/morin_kaist_logo.png"
      alt="KAIST MORIN 연구실 로고"
      width="344"
      height="219"
    />
    <h1>MORIN GPU 서버</h1>
    <p class="sub">연구실 GPU 예약 시스템</p>
  </header>
</template>

<style scoped>
.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  margin: 0.5rem 0 1.25rem;
  text-align: center;
}

/* width/height 를 적어 두면 그림이 늦게 떠도 자리가 밀리지 않는다.
   실제 크기는 아래 CSS 가 정한다. */
.logo {
  width: 170px;
  height: auto;
  margin-bottom: 0.6rem;
}

h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: #1c3f74; /* 로고의 KAIST 파랑과 맞춘 색 */
}

.sub {
  margin: 0;
  font-size: 0.9rem;
  color: var(--muted);
}

/* 휴대폰에서는 로고와 제목을 조금 작게 */
@media (max-width: 480px) {
  .brand {
    margin: 0.25rem 0 1rem;
  }

  .logo {
    width: 132px;
  }

  h1 {
    font-size: 1.25rem;
  }

  .sub {
    font-size: 0.82rem;
  }
}
</style>
