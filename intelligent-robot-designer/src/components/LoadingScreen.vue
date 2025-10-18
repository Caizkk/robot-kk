<template>
  <div class="loading-overlay">
    <div class="loading-container">
      <img src="/logo.ico" alt="Logo" class="loading-logo" />
      <div class="title-container">
        <h1 class="main-title">和元智擎机器人</h1>
        <p class="subtitle">引领智能自动化的未来</p>
      </div>
      <div class="status-container">
         <div class="status-spinner"></div>
         <p class="loading-text">{{ text }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  text: {
    type: String,
    default: '正在连接服务, 请稍候...'
  }
});
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  /* Updated background to a light white-blue gradient */
  background: linear-gradient(135deg, #ffffff 0%, #e6f4ff 100%);
  z-index: 9999;
  opacity: 0;
  animation: fadeIn 0.5s forwards;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 3rem;
  text-align: center;
}

.loading-logo {
  height: 90px;
  width: 90px;
  margin-bottom: 1rem;
  animation: subtle-pulse 2.5s infinite cubic-bezier(0.4, 0, 0.6, 1);
}

.title-container {
  margin-bottom: 2rem;
}

.main-title {
  font-size: 2.25rem;
  font-weight: 700;
  /* Reverted to dark gradient text for light background */
  letter-spacing: 3px;
  margin: 0;
  background: -webkit-linear-gradient(45deg, #0958d9, #1677ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  font-size: 1.1rem;
  font-weight: 400;
  /* Reverted to dark text for light background */
  color: #4b5563;
  margin-top: 0.75rem;
  letter-spacing: 1.5px;
}

.status-container {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
    margin-top: 1rem;
}

.status-spinner {
  width: 20px;
  height: 20px;
  /* Reverted to blue spinner for light background */
  border: 3px solid rgba(22, 119, 255, 0.2);
  border-top-color: #1677ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  font-size: 0.95rem;
  font-weight: 500;
  /* Reverted to dark text for light background */
  color: #374151;
}

@keyframes fadeIn {
  to {
    opacity: 1;
  }
}

@keyframes subtle-pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

