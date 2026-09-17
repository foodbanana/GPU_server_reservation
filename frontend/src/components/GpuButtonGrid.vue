<script setup>
// 단주기 GPU 6개 / 장주기 GPU 6개 버튼을 구분해서 배치한다 (SPEC 8장).
import { computed } from 'vue'

const props = defineProps({
  gpus: { type: Array, required: true },
})

const 단주기 = computed(() => props.gpus.filter((g) => g.category === 'short'))
const 장주기 = computed(() => props.gpus.filter((g) => g.category === 'long'))
</script>

<template>
  <section class="group">
    <h2>단주기 GPU 예약</h2>
    <p class="hint">짧게 쓸 작업용입니다. 예약 시간 제한은 없으니 서로 협의해서 쓰세요.</p>
    <div class="grid">
      <RouterLink
        v-for="gpu in 단주기"
        :key="gpu.id"
        class="gpu-btn short"
        :to="{ name: 'reserve-gpu', params: { gpuId: gpu.id } }"
      >
        <span class="server">서버 {{ gpu.server_no }}</span>
        <span class="index">GPU {{ gpu.gpu_index }}</span>
        <span class="model">{{ gpu.model }}</span>
      </RouterLink>
    </div>
  </section>

  <section class="group">
    <h2>장주기 GPU 예약</h2>
    <p class="hint">며칠씩 오래 돌릴 작업용입니다. 예약 시간 제한은 없습니다.</p>
    <div class="grid">
      <RouterLink
        v-for="gpu in 장주기"
        :key="gpu.id"
        class="gpu-btn long"
        :to="{ name: 'reserve-gpu', params: { gpuId: gpu.id } }"
      >
        <span class="server">서버 {{ gpu.server_no }}</span>
        <span class="index">GPU {{ gpu.gpu_index }}</span>
        <span class="model">{{ gpu.model }}</span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.group {
  margin-bottom: 1.75rem;
}

h2 {
  font-size: 1.1rem;
  margin: 0 0 0.25rem;
}

.grid {
  display: grid;
  /* 휴대폰에서는 2칸, 넓은 화면에서는 3칸 */
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.6rem;
  margin-top: 0.75rem;
}

.gpu-btn {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--gray-line);
  background: #fff;
  text-decoration: none;
  color: inherit;
  border-left-width: 5px;
}

.gpu-btn:hover {
  background: #f0f4fa;
}

.gpu-btn.short {
  border-left-color: #1a73e8;
}

.gpu-btn.long {
  border-left-color: #6a3fb5;
}

.server {
  font-size: 0.8rem;
  color: var(--muted);
}

.index {
  font-weight: 700;
  font-size: 1.05rem;
}

.model {
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
