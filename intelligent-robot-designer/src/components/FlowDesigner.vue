<script setup>
import { ref, defineExpose } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

// 导入自定义节点组件
import ActionNode from './nodes/ActionNode.vue'

// 导入 VueFlow 及其插件的样式
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

let id = 4 // 用于为新节点生成唯一ID的计数器
const { 
  onPaneReady, 
  onConnect, 
  addEdges, 
  project, // project 函数用于将屏幕坐标转换为画布坐标
  addNodes,  // addNodes 函数用于向画布添加新节点
  nodes,     // 从 useVueFlow 获取响应式的 nodes 和 edges
  edges
} = useVueFlow()

// 初始节点数据
nodes.value = [
  { id: '1', type: 'input', label: '开始', position: { x: 250, y: 5 } },
  { 
    id: '2', 
    type: 'action', // 使用 'action' 自定义类型
    label: '打开浏览器', 
    position: { x: 150, y: 100 },
    data: { label: '打开浏览器', params: 'https://example.com' } // `data` 对象会作为 prop 传递给自定义节点
  },
  { 
    id: '3', 
    type: 'action', // 使用 'action' 自定义类型
    label: '输入文本', 
    position: { x: 150, y: 220 },
    data: { label: '输入文本', params: 'input[name="q"], "RPA"' }
  },
  { id: '4', type: 'output', label: '结束', position: { x: 250, y: 340 } },
]

// 初始连线数据
edges.value = [
  { id: 'e1-2', source: '1', target: '2' },
  { id: 'e2-3', source: '2', target: '3', animated: true },
  { id: 'e3-4', source: '3', target: '4' },
]

/**
 * 当画布准备就绪时触发
 */
onPaneReady(({ fitView }) => {
  // 自动调整视图以适应所有节点
  fitView()
})

/**
 * 当用户在画布上连接两个节点时触发
 */
onConnect((params) => addEdges(params))

/**
 * 当有可拖拽的元素在画布上移动时触发
 */
const onDragOver = (event) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

/**
 * 当元素被放置到画布上时触发
 */
const onDrop = (event) => {
  // 从 dataTransfer 中获取节点数据
  const data = JSON.parse(event.dataTransfer?.getData('application/vueflow'))
  
  // 将放置点的屏幕坐标转换为画布内的坐标
  // 减去 40px 是为了调整鼠标指针相对于节点左上角的位置偏差
  const { x, y } = project({ x: event.clientX, y: event.clientY - 40 })

  const newNode = {
    id: `node-${++id}`, // 创建唯一 ID
    type: data.type,
    position: { x, y },
    label: `${data.label}`,
    data: { label: data.label, params: '请配置参数' } // 设置节点的初始数据
  }
  
  // 将新节点添加到画布
  addNodes([newNode])
}

/**
 * 暴露 getFlowData 方法给父组件，用于保存流程
 */
defineExpose({
  getFlowData: () => ({
    nodes: nodes.value,
    edges: edges.value,
  }),
})
</script>

<template>
  <div class="flow-designer-wrapper" @dragover="onDragOver" @drop="onDrop">
    <VueFlow>
      <!-- 背景 -->
      <Background />
      <!-- 小地图 -->
      <MiniMap />
      <!-- 控制器 -->
      <Controls />

      <!-- 定义自定义节点的渲染方式 -->
      <!-- 当遇到 type='action' 的节点时，会使用这个模板 -->
      <template #node-action="props">
        <ActionNode :data="props.data" />
      </template>
    </VueFlow>
  </div>
</template>

<style>
.flow-designer-wrapper {
  height: 100%;
  width: 100%;
}
</style>

