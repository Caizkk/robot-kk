<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Minus, Close } from '@element-plus/icons-vue'

// 窗口控制函数
const minimizeWindow = () => {
  // @ts-ignore - 使用preload中定义的API
  window.electronAPI.windowControl.minimize()
}

const closeWindow = () => {
  // @ts-ignore - 使用preload中定义的API
  window.electronAPI.windowControl.close()
}

// 拖动窗口函数
const dragWindow = () => {
  // @ts-ignore - 使用preload中定义的API
  window.electronAPI.windowControl.drag()
}

// 在组件挂载时设置拖动区域
onMounted(() => {
  const titleBar = document.querySelector('.title-bar')
  if (titleBar) {
    titleBar.addEventListener('mousedown', dragWindow)
  }
})
</script>

<template>
  <div class="title-bar">
    <div class="title-text">
      <img src="/logo.ico" alt="Logo" class="title-logo" />
      <span>和元智擎机器人</span>
    </div>
    <div class="window-controls">
      <div class="control-button minimize ripple" @click="minimizeWindow">
        <el-icon><Minus /></el-icon>
      </div>
      <div class="control-button close ripple" @click="closeWindow">
        <el-icon><Close /></el-icon>
      </div>
    </div>
  </div>
</template>

<style scoped>
.title-bar {
  height: 44px;
  background: linear-gradient(
    135deg,
    #0958d9 0%,
    #1677ff 100%
  );
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  -webkit-app-region: drag;
  user-select: none;
  box-shadow: 0 2px 12px rgba(9, 88, 217, 0.35);
  position: relative;
  z-index: 1000;
  cursor: move; /* 添加移动光标提示用户可拖动 */
}

.title-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    to right,
    rgba(255, 255, 255, 0.15),
    rgba(255, 255, 255, 0.05) 50%,
    transparent
  );
  pointer-events: none;
}

.title-text {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 16px;
  letter-spacing: 0.5px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.title-logo {
  height: 24px;
  width: 24px;
  margin-right: 12px;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
}

.window-controls {
  display: flex;
  -webkit-app-region: no-drag;
  gap: 4px;
}

.control-button {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  cursor: pointer;
  background-color: transparent;
  position: relative;
  overflow: hidden;
}

.control-button:hover {
  background-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.control-button:active {
  transform: translateY(0);
}

.control-button.minimize:hover {
  background-color: rgba(255, 255, 255, 0.2);
}

.control-button.close:hover {
  background-color: #dc2626;
}

.control-button .el-icon {
  font-size: 18px;
  color: white;
  transition: all var(--transition-fast);
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
}

.control-button:hover .el-icon {
  transform: scale(1.1);
}

.control-button:active .el-icon {
  transform: scale(1);
}
</style> 