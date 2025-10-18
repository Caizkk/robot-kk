<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { Plus, Delete, Document, CaretRight, VideoPause, ArrowLeft, Search, Clock, Calendar, CircleClose } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ProcessService } from '../services/process'
import { ProcessItem, StatusCode, ProcessInstance } from '../types/api'

interface RobotScript {
  id: number
  name: string
  version: string
  status: 'running' | 'stopped'
  createdAt: string
  updatedAt: string
  runningCount: number
  pausedCount: number
  records?: RobotRecord[]
}

interface RobotRecord {
  id: number
  scriptId: number
  startTime: string
  endTime: string | null
  status: 'running' | 'paused' | 'completed' | 'failed'
  log_path: string | null
  version: string
  duration: string
}

// 机器人流程列表
const robotScripts = ref<RobotScript[]>([])
const currentPage = ref(1)
const pageSize = ref(6)
const totalScripts = ref(0)
const searchKeyword = ref('')

// 当前选中的流程和记录
const currentScript = ref<RobotScript | null>(null)
const showRecords = ref(false)
const currentRecord = ref<RobotRecord | null>(null)
const selectedScriptId = ref<number | null>(null)
const selectedRecordId = ref<number | null>(null)

// 运行记录分页
const recordsCurrentPage = ref(1)
const recordsPageSize = ref(6)
const totalRecords = ref(0)

// 导入流程对话框
const importDialogVisible = ref(false)
const importForm = reactive({
  name: '',
  file: null as File | null,
  filePath: '',
  importType: 'new', // 'new' 或 'existing'
  selectedProcessId: null as number | null
})

// 表单引用
const importFormRef = ref()

// 流程选择列表
const existingProcesses = ref<{id: number, name: string}[]>([])

// 导入表单验证规则
const importRules = {
  name: [
    { required: true, message: '请输入流程名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  file: [
    { required: true, message: '请选择流程文件', trigger: 'change' }
  ],
  selectedProcessId: [
    { required: true, message: '请选择要更新的流程', trigger: 'change' }
  ]
}

// 对话框宽度响应式
const dialogWidth = ref('500px')

// 数据加载
onMounted(() => {
  loadRobotScripts()
  updateDialogWidth()
  window.addEventListener('resize', updateDialogWidth)
})

// 加载机器人流程列表
const loadRobotScripts = async () => {
  try {
    const response = await ProcessService.getProcessList(currentPage.value, pageSize.value, searchKeyword.value || undefined)
    
    if (response.code === StatusCode.SUCCESS && response.data) {
      const processItems = response.data.data || []
      
      robotScripts.value = processItems.map(item => ({
        id: item.id,
        name: item.name,
        version: item.version,
        status: 'stopped',
        createdAt: item.create_time,
        updatedAt: item.update_time,
        runningCount: item.run_count,
        pausedCount: item.pause_count
      }))
      
      totalScripts.value = response.data.total
    } else {
      ElMessage.error(response.message || '加载流程列表失败')
    }
  } catch (error) {
    console.error('加载流程列表出错:', error)
    ElMessage.error('加载流程列表失败')
  }
}

// 加载特定流程的运行记录
const loadScriptRecords = async (scriptId: number) => {
  if (!currentScript.value) return;

  try {
    const response = await ProcessService.getInstanceList(recordsCurrentPage.value, recordsPageSize.value, scriptId);
    if (response.code === StatusCode.SUCCESS && response.data) {
      currentScript.value.records = response.data.data.map(instance => {
        // 安全地处理时长
        const duration = instance.duration ?? 0;
        const durationMinutes = Math.floor(duration / 60);
        const durationSeconds = duration % 60;
        
        // 根据 status 和 result 确定状态
        let status: 'running' | 'paused' | 'completed' | 'failed' = 'running';
        if (instance.status === '1') { // "1" 表示已完成
            status = instance.result === '1' ? 'completed' : 'failed';
        } else { // "0" 表示正在运行
            status = 'running';
        }

        return {
          id: instance.id,
          scriptId: instance.process_id,
          startTime: new Date(instance.start_time).toLocaleString(),
          endTime: instance.end_time ? new Date(instance.end_time).toLocaleString() : null,
          status: status,
          log_path: instance.log_path,
          version: currentScript.value?.version || 'N/A',
          duration: `${durationMinutes}分${durationSeconds}秒`,
        };
      });
      totalRecords.value = response.data.total;
    } else {
      ElMessage.error(response.message || '加载运行记录失败');
      currentScript.value.records = [];
      totalRecords.value = 0;
    }
  } catch (error) {
    console.error('加载运行记录出错:', error);
    ElMessage.error('加载运行记录失败');
    currentScript.value.records = [];
    totalRecords.value = 0;
  }
};


// 分页展示的流程
const paginatedScripts = computed(() => robotScripts.value)

// 总的过滤后的流程数量
const filteredTotalScripts = computed(() => totalScripts.value)

// 处理页码变化
const handleCurrentChange = (val: number) => {
  currentPage.value = val
  loadRobotScripts()
}

// 处理搜索
const handleSearch = () => {
  currentPage.value = 1
  loadRobotScripts()
}

// 打开导入流程对话框
const openImportDialog = () => {
  importForm.name = ''
  importForm.file = null
  importForm.filePath = ''
  importForm.importType = 'new'
  importForm.selectedProcessId = null
  
  loadExistingProcesses()
  
  importDialogVisible.value = true
}

// 加载现有流程列表
const loadExistingProcesses = async () => {
  try {
    const response = await ProcessService.getAllProcessIdNames()
    if (response.code === StatusCode.SUCCESS && response.data) {
      existingProcesses.value = response.data.data || []
    } else {
      console.error('获取流程列表失败:', response.message)
      existingProcesses.value = []
    }
  } catch (error) {
    console.error('获取流程列表出错:', error)
    existingProcesses.value = []
  }
}

// 选择文件
const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (file) {
    if (!file.name.toLowerCase().endsWith('.robot')) {
      ElMessage.warning('请选择.robot格式的文件')
      target.value = ''
      return
    }
    
    importForm.file = file
    importForm.filePath = file.name
  }
}

// 导入机器人流程
const submitImportForm = async () => {
  if (!importForm.file) {
    ElMessage.warning('请选择流程文件')
    return
  }
  
  if (importForm.importType === 'new' && !importForm.name) {
    ElMessage.warning('请输入流程名称')
    return
  }
  
  if (importForm.importType === 'existing' && !importForm.selectedProcessId) {
    ElMessage.warning('请选择要更新的流程')
    return
  }
  
  try {
    const processName = importForm.importType === 'new'
      ? importForm.name
      : existingProcesses.value.find(p => p.id === importForm.selectedProcessId)?.name || '';

    const response = await ProcessService.importProcess(
      importForm.file,
      processName,
      importForm.importType === 'existing' ? importForm.selectedProcessId! : undefined
    )
      
    if (response.code === StatusCode.SUCCESS) {
      ElMessage.success(importForm.importType === 'new' ? '流程导入成功' : '流程更新成功')
      importDialogVisible.value = false
      loadRobotScripts()
    } else {
      ElMessage.error(response.message || (importForm.importType === 'new' ? '流程导入失败' : '流程更新失败'))
    }
  } catch (error) {
    console.error('导入/更新流程出错:', error)
    ElMessage.error('操作失败')
  }
}

// 触发文件选择
const triggerFileSelect = () => {
  openImportDialog()
}

// 选择导入文件
const selectImportFile = () => {
  const fileInput = document.getElementById('importFileInput') as HTMLInputElement
  if (fileInput) {
    fileInput.click()
  }
}

// 删除流程
const deleteScript = (script: RobotScript) => {
  ElMessageBox.confirm(
    `确定要删除流程 "${script.name}" 吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      const response = await ProcessService.deleteProcess(script.id)
      if (response.code === StatusCode.SUCCESS) {
        loadRobotScripts()
        ElMessage.success('删除成功')
      } else {
        ElMessage.error(response.message || '删除失败')
      }
    } catch (error) {
      console.error('删除流程出错:', error)
      ElMessage.error('删除流程失败')
    }
  }).catch(() => {})
}

// 运行流程
const toggleScriptRunning = async (script: RobotScript) => {
  const totalInstances = script.runningCount + script.pausedCount;
  if (totalInstances >= 5) {
    ElMessage.error('最多同时运行5个任务');
    return;
  }
  
  try {
    const response = await ProcessService.startProcess(script.id);
    if (response.code === StatusCode.SUCCESS) {
      ElMessage.success('流程已启动');
      loadRobotScripts();
    } else {
      ElMessage.error(response.message || '启动流程失败');
    }
  } catch (error) {
    console.error('启动流程出错:', error);
    ElMessage.error('启动流程失败');
  }
}

// 查看运行记录
const viewRecords = (script: RobotScript) => {
  currentScript.value = script
  selectedScriptId.value = script.id
  recordsCurrentPage.value = 1
  showRecords.value = true
  loadScriptRecords(script.id)
}

// 打开本地日志文件
const openLocalLogFile = async (logPath: string) => {
  try {
    // @ts-ignore
    if (window.electronAPI) {
      // @ts-ignore
      const result = await window.electronAPI.openLogFile(logPath)
      if (!result.success) {
        ElMessage.error('打开日志文件失败')
      }
    } else {
      ElMessage.warning('当前环境不支持打开本地文件');
    }
  } catch (error) {
    ElMessage.error('打开日志文件失败')
  }
}

// 查看日志
const viewLogs = (record: RobotRecord) => {
  currentRecord.value = record
  selectedRecordId.value = record.id
  
  if (record.log_path) {
    openLocalLogFile(record.log_path)
  } else {
    ElMessage.warning('该记录没有可用的日志文件路径');
  }
}


// 返回到流程列表
const backToScripts = () => {
  const selectedRecordCards = document.querySelectorAll('.record-card.selected');
  selectedRecordCards.forEach(card => {
    card.classList.remove('selected');
  });
  
  showRecords.value = false;
  currentScript.value = null;
  selectedScriptId.value = null;
  selectedRecordId.value = null;
  recordsCurrentPage.value = 1;
  totalRecords.value = 0;
}

// 分页展示的记录
const paginatedRecords = computed(() => {
  return currentScript.value?.records || []
})

// 处理记录页码变化
const handleRecordsCurrentChange = (val: number) => {
  recordsCurrentPage.value = val
  if (currentScript.value) {
    loadScriptRecords(currentScript.value.id)
  }
}

// 选择流程
const selectScript = (script: RobotScript) => {
  const selectedCards = document.querySelectorAll('.script-card.selected');
  selectedCards.forEach(card => {
    card.classList.remove('selected');
  });
  
  selectedScriptId.value = script.id;
  
  setTimeout(() => {
    const currentCard = document.querySelector(`.script-card[data-script-id="${script.id}"]`);
    if (currentCard) {
      currentCard.classList.add('selected');
    }
  }, 0);
}

// 选择记录
const selectRecord = (record: RobotRecord) => {
  const selectedCards = document.querySelectorAll('.record-card.selected');
  selectedCards.forEach(card => {
    card.classList.remove('selected');
  });
  
  selectedRecordId.value = record.id;
  
  setTimeout(() => {
    const currentCard = document.querySelector(`.record-card[data-record-id="${record.id}"]`);
    if (currentCard) {
      currentCard.classList.add('selected');
    }
  }, 0);
}

// 更新对话框宽度
const updateDialogWidth = () => {
  const screenWidth = window.innerWidth
  if (screenWidth < 576) {
    dialogWidth.value = '95%'
  } else if (screenWidth < 768) {
    dialogWidth.value = '80%'
  } else {
    dialogWidth.value = '500px'
  }
}

watch(searchKeyword, (newValue, oldValue) => {
  if (newValue !== oldValue) {
    handleSearch();
  }
});
</script>

<template>
  <div class="run-page">
    <div v-if="!showRecords" class="script-list-container">
      <div class="fixed-action-bar">
        <div class="action-bar">
          <div class="search-container">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索流程"
              class="search-input"
              @input="handleSearch"
              clearable
            >
              <template #prefix>
                <el-icon class="search-icon"><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <el-button type="primary" class="import-button" @click="triggerFileSelect">
            <el-icon class="button-icon"><Plus /></el-icon>
            <span>导入流程</span>
          </el-button>
          <input
            type="file"
            id="scriptFileInput"
            style="display: none"
            accept=".js,.py,.json"
            @change="handleFileChange"
          />
        </div>
      </div>
              <div class="card-container with-fixed-action-bar">
          
          <div v-if="robotScripts.length === 0" class="empty-state">
            <div class="empty-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                <polyline points="13 2 13 9 20 9"></polyline>
              </svg>
            </div>
            <div class="empty-text">暂无流程</div>
            <div class="empty-subtext">点击"导入流程"按钮添加新的流程</div>
          </div>
          
          <el-row :gutter="24" v-else>
          <el-col :xs="24" :sm="24" :md="12" :lg="8" v-for="script in paginatedScripts" :key="script.id">
            <el-card 
              class="script-card" 
              shadow="hover" 
              :class="{ selected: selectedScriptId === script.id }" 
              @click.stop="selectScript(script)"
              :data-script-id="script.id"
            >
              <div class="card-header">
                <div class="card-title">{{ script.name }}</div>
              </div>

              <div class="card-info">
                <div class="card-info-header">
                  <div class="version-item">
                    <span class="version-badge">{{ script.version }}</span>
                  </div>
                  <div class="stats-badges">
                    <span class="stats-badge success">运行 {{ script.runningCount }}</span>
                    <span class="stats-badge paused">暂停 {{ script.pausedCount }}</span>
                  </div>
                </div>
                <div class="info-item">
                  <span class="info-label">创建时间:</span>
                  <span class="info-value">{{ new Date(script.createdAt).toLocaleString() }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">更新时间:</span>
                  <span class="info-value">{{ new Date(script.updatedAt).toLocaleString() }}</span>
                </div>
              </div>

              <div class="card-footer">
                <div class="card-actions">
                  <el-tooltip content="启动" placement="top">
                    <el-button
                      circle
                      type="primary"
                      :icon="CaretRight"
                      @click.stop="toggleScriptRunning(script)"
                    />
                  </el-tooltip>
                  <el-tooltip content="查看记录" placement="top">
                    <el-button
                      circle
                      type="info"
                      :icon="Document"
                      @click.stop="viewRecords(script)"
                    />
                  </el-tooltip>
                  <el-tooltip content="删除" placement="top">
                    <el-button
                      circle
                      type="danger"
                      :icon="Delete"
                      @click.stop="deleteScript(script)"
                      :disabled="script.runningCount > 0"
                    />
                  </el-tooltip>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
      
      <div class="pagination-container" v-if="robotScripts.length > 0">
        <div class="custom-pagination">
          <div class="pagination-btn prev" @click="currentPage > 1 && handleCurrentChange(currentPage - 1)">
            <span>上一页</span>
          </div>
          <div class="pagination-info">
            <span>第<span class="page-highlight">{{ currentPage }}</span>/<span class="page-total">{{ Math.max(1, Math.ceil(filteredTotalScripts / pageSize)) }}</span>页 每页<span class="page-highlight">{{ pageSize }}</span>条 共<span class="data-count">{{ filteredTotalScripts }}</span>条数据</span>
          </div>
          <div class="pagination-btn next" @click="currentPage < Math.ceil(filteredTotalScripts / pageSize) && handleCurrentChange(currentPage + 1)">
            <span>下一页</span>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="showRecords" class="records-container">
      <div class="page-header">
        <div class="header-with-back">
          <div class="back-button" @click="backToScripts">
            <el-icon class="back-icon"><ArrowLeft /></el-icon>
          </div>
          <div class="page-title-container">
            <h2 class="page-title">{{ currentScript?.name }} - 运行记录</h2>
            <div class="title-underline"></div>
          </div>
        </div>
      </div>
      
      <div class="card-container">
        <el-row :gutter="24">
          <el-col :xs="24" :sm="24" :md="12" :lg="8" v-for="record in paginatedRecords" :key="record.id" style="height: 100%">
            <el-card 
              class="record-card" 
              shadow="hover" 
              :class="{ selected: selectedRecordId === record.id }" 
              @click.stop="selectRecord(record)"
              :data-record-id="record.id"
              :style="{ position: 'relative' }"
            >
              <div class="card-header">
                <div class="record-status">
                  <el-tag 
                    :type="record.status === 'completed' ? 'success' : record.status === 'failed' ? 'danger' : 'info'"
                    effect="dark"
                  >
                    {{ record.status === 'completed' ? '成功' : record.status === 'failed' ? '失败' : '运行中' }}
                  </el-tag>
                </div>
              </div>
              <div class="card-info">
                <div class="card-info-header">
                  <div class="version-item">
                    <span class="version-badge">{{ record.version }}</span>
                  </div>
                </div>
                <div class="info-item">
                  <el-icon class="info-icon"><Calendar /></el-icon>
                  <span class="info-label">开始时间:</span>
                  <span class="info-value">{{ record.startTime }}</span>
                </div>
                <div class="info-item">
                  <el-icon class="info-icon"><Calendar /></el-icon>
                  <span class="info-label">结束时间:</span>
                  <span class="info-value">{{ record.endTime || '--' }}</span>
                </div>
                <div class="info-item">
                  <el-icon class="info-icon"><Clock /></el-icon>
                  <span class="info-label">运行时长:</span>
                  <span class="info-value">{{ record.duration }}</span>
                </div>
                </div>
              <div v-if="record.status === 'completed' || record.status === 'failed'"
                class="result-badge"
                :class="record.status === 'completed' ? 'result-success' : 'result-failed'">
                <el-icon class="result-icon">
                  <svg t="1716036646730" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4276" width="16" height="16">
                    <path :fill="record.status === 'completed' ? '#ffffff' : '#ffffff'" d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m193.5 301.7l-210.6 292a31.8 31.8 0 0 1-51.7 0L318.5 484.9c-3.8-5.3 0-12.7 6.5-12.7h46.9c10.2 0 19.9 4.9 25.9 13.3l71.2 98.8 157.2-218c6-8.3 15.6-13.3 25.9-13.3H699c6.5 0 10.3 7.4 6.5 12.7z" p-id="4277"></path>
                  </svg>
                </el-icon>
                <span class="result-text">{{ record.status === 'completed' ? '成功' : '失败' }}</span>
              </div>
              
              <div class="card-footer">
                <div class="card-actions">
                  <el-tooltip content="查看日志" placement="top">
                    <el-button
                      circle
                      type="primary"
                      :icon="Document"
                      @click.stop="viewLogs(record)"
                      :disabled="!record.log_path"
                    />
                  </el-tooltip>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
      
      <div class="pagination-container">
        <div class="custom-pagination">
          <div class="pagination-btn prev" @click="recordsCurrentPage > 1 && handleRecordsCurrentChange(recordsCurrentPage - 1)">
            <span>上一页</span>
          </div>
          <div class="pagination-info">
            <span>第<span class="page-highlight">{{ recordsCurrentPage }}</span>/<span class="page-total">{{ Math.max(1, Math.ceil(totalRecords / recordsPageSize)) }}</span>页 每页<span class="page-highlight">{{ recordsPageSize }}</span>条 共<span class="data-count">{{ totalRecords }}</span>条数据</span>
          </div>
          <div class="pagination-btn next" @click="recordsCurrentPage < Math.ceil(totalRecords / recordsPageSize) && handleRecordsCurrentChange(recordsCurrentPage + 1)">
            <span>下一页</span>
          </div>
        </div>
      </div>
    </div>
    

    
    <el-dialog
      v-model="importDialogVisible"
      title="导入流程"
      :width="dialogWidth"
      class="import-dialog"
      :close-on-click-modal="false"
      :destroy-on-close="true"
    >
      <div class="compact-form">
        <div class="form-row">
          <div class="form-label required">流程文件</div>
          <div class="file-upload-container">
            <el-input v-model="importForm.filePath" placeholder="请选择.robot文件" readonly />
            <el-button type="primary" @click="selectImportFile">
              选择文件
            </el-button>
          </div>
          <input
            type="file"
            id="importFileInput"
            style="display: none"
            accept=".robot"
            @change="handleFileChange"
          />
        </div>
        
        <div class="form-row">
          <div class="form-label">导入方式</div>
          <div class="radio-container">
            <el-radio v-model="importForm.importType" label="new">新建流程</el-radio>
            <el-radio v-model="importForm.importType" label="existing" :disabled="existingProcesses.length === 0">更新已有流程</el-radio>
          </div>
        </div>
        
        <div v-if="importForm.importType === 'new'" class="form-row">
          <div class="form-label required">流程名称</div>
          <el-input v-model="importForm.name" placeholder="请输入流程名称" />
        </div>
        
        <div v-else class="form-row">
          <div class="form-label required">选择流程</div>
          <el-select v-model="importForm.selectedProcessId" placeholder="请选择要更新的流程" style="width: 100%">
            <el-option
              v-for="process in existingProcesses"
              :key="process.id"
              :label="process.name"
              :value="process.id"
            />
          </el-select>
        </div>
      </div>
      
      <div class="dialog-divider"></div>
      
      <div class="dialog-footer">
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitImportForm">导入</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.run-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f0f2f5;
  padding: 0.5rem 1rem 0 1rem;
  color: #333;
  position: relative;
  overflow: hidden;
}

.script-list-container,
.records-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: visible;
  margin-top: -0.25rem;
}

.script-list-container {
  position: relative;
}

.card-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 0.25rem;
  margin-bottom: 0;
  padding-bottom: 1rem;
  width: 100%;
  padding-top: 0.125rem;
}

.fixed-action-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: transparent;
  padding: 0.5rem 0;
  margin-bottom: 0.5rem;
  backdrop-filter: blur(8px);
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0;
  gap: 1rem;
  flex-wrap: nowrap;
}

.card-container.with-fixed-action-bar {
  padding-top: 0.5rem;
}

.search-container {
  flex: 1;
  max-width: none;
}

.search-input {
  width: 100%;
}

.search-input :deep(.el-input__wrapper) {
  background-color: #ffffff;
  box-shadow: none;
  border: 1px solid #e6e6e6;
  border-radius: 20px;
  height: 32px;
  transition: all 0.3s ease;
}

.search-input :deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc;
}

.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: #1677ff;
  box-shadow: 0 0 0 1px rgba(22, 119, 255, 0.1);
}

.search-input :deep(.el-input__inner) {
  padding-left: 0.5rem;
}

.search-icon {
  color: #909399;
  font-size: 1rem;
  margin-left: 0.5rem;
}

.import-button {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 1.5rem;
  border-radius: 20px;
  font-weight: 500;
  font-size: 0.875rem;
  background-color: #1677ff;
  border: none;
  transition: all 0.3s ease;
  box-shadow: 0 2px 6px rgba(22, 119, 255, 0.2);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 110px;
}

.import-button:hover {
  background-color: #4096ff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.3);
}

.button-icon {
  margin-right: 0.375rem;
  font-size: 0.875rem;
}

.script-card, .record-card {
  margin-bottom: 1.25rem;
  transition: all 0.25s ease;
  border-radius: 0.5rem;
  border: 1px solid #d0d7e3;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08), 0 0 2px rgba(0, 0, 0, 0.1);
  transform: translateZ(0);
  position: relative;
  overflow: hidden;
  cursor: pointer;
  background: #ffffff;
}

.record-card {
  margin-bottom: 1rem;
}

.script-card::before, .record-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 0;
  background-color: #1677ff;
  transition: width 0.25s ease;
  z-index: 1;
}

.script-card:hover, .record-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(22, 119, 255, 0.25), 0 0 3px rgba(22, 119, 255, 0.2);
  border-color: #bae0ff;
}

.script-card:hover .card-header, .record-card:hover .card-header {
  background-color: #e6f4ff;
}

.script-card:hover .card-info, .record-card:hover .card-info,
.script-card:hover .card-footer, .record-card:hover .card-footer {
  background-color: #f0f7ff;
}

.script-card:hover .card-title, .record-card:hover .card-title {
  color: #0958d9;
}

.script-card.selected, .record-card.selected {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(22, 119, 255, 0.25), 0 0 3px rgba(22, 119, 255, 0.2);
  border-color: #1677ff;
}

.script-card.selected .card-header, .record-card.selected .card-header {
  background-color: #bae0ff;
}

.script-card.selected .card-info, .record-card.selected .card-info,
.script-card.selected .card-footer, .record-card.selected .card-footer {
  background-color: #e6f4ff;
}

.script-card.selected .card-title, .record-card.selected .card-title {
  color: #0958d9;
  font-weight: 700;
}

.script-card.selected::before, .record-card.selected::before {
  width: 4px;
}

.card-header, .card-info, .card-footer {
  position: relative;
  z-index: 2;
  transition: background-color 0.25s ease;
}

.card-header {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f0f7ff;
  border-radius: 0.5rem 0.5rem 0 0;
  height: 40px;
  overflow: hidden;
  transition: background-color 0.25s ease;
}

.card-header::after {
  content: none;
}

.script-card:hover .card-header::after, .record-card:hover .card-header::after {
  transform: none;
}

.card-title {
  font-weight: 700;
  font-size: 1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #1677ff;
}

.card-info {
  padding: 0.5rem 0.75rem;
  background-color: #fff;
}

.card-info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.info-item {
  margin-bottom: 0.125rem;
  display: flex;
  font-size: 0.8125rem;
}

.info-label {
  font-weight: 500;
  color: #606266;
  width: 4.6875rem;
}

.info-value {
  color: #333;
  flex: 1;
}

.card-footer {
  padding: 0.375rem 0.75rem;
  border-top: 1px solid #e4e7ed;
  background-color: #fff;
  border-radius: 0 0 0.5rem 0.5rem;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.625rem;
  align-items: center;
  height: 2rem;
}

.pagination-container {
  display: flex;
  justify-content: center;
  padding: 0.75rem 0;
  margin-top: auto;
  position: sticky;
  bottom: 0;
  background-color: rgba(245, 247, 250, 0.95);
  backdrop-filter: blur(8px);
  z-index: 9;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
}

.custom-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 2rem;
  padding: 0.25rem 0;
  width: 100%;
  max-width: 400px;
}

.pagination-btn {
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 0.25rem;
  color: #606266;
  font-weight: 500;
  padding: 0 0.75rem;
  min-width: 4.375rem;
  text-align: center;
  height: 2rem;
  line-height: 2rem;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.pagination-btn:hover {
  color: #1976d2;
  border-color: #c6e2ff;
}

.pagination-btn:active {
  background-color: #e8f4ff;
}

.pagination-btn.prev {
  margin-right: 0.3125rem;
  padding: 0 0.9375rem;
}

.pagination-btn.next {
  margin-left: 0.3125rem;
  padding: 0 0.9375rem;
}

.pagination-info {
  padding: 0 0.3125rem;
  height: 2rem;
  line-height: 2rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #606266;
  text-align: center;
  flex: 1;
}

.file-upload-container {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.execution-summary {
  display: flex;
  gap: 1.25rem;
  align-items: center;
}

.success-stat, .failure-stat {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.625rem;
  border-radius: 0.375rem;
}

.success-stat {
  background-color: rgba(46, 125, 50, 0.1);
}

.failure-stat {
  background-color: rgba(211, 47, 47, 0.1);
}

.stat-label {
  font-weight: 500;
  font-size: 0.875rem;
}

.stat-value {
  font-weight: 700;
  font-size: 1rem;
}

.success-stat .stat-value {
  color: #2e7d32;
}

.failure-stat .stat-value {
  color: #d32f2f;
}

.stat-unit {
  font-size: 0.875rem;
  color: #606266;
}

@media (max-width: 768px) {
  .action-bar {
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: nowrap;
  }
  
  .search-container {
    flex: 1;
  }
  
  .import-button {
    padding: 0 1.25rem;
    min-width: 100px;
  }
}

@media (max-width: 576px) {
  .run-page {
    padding: 0.25rem 0.5rem 0 0.5rem;
  }
  
  .action-bar {
    flex-wrap: nowrap;
  }
  
  .import-button {
    padding: 0 1rem;
    min-width: 90px;
  }
  
  .card-header {
    height: auto;
    min-height: 40px;
    flex-wrap: wrap;
    padding: 0.375rem 0.5rem;
  }
  
  .card-title {
    font-size: 0.9375rem;
  }
  
  .info-item {
    font-size: 0.75rem;
  }
  
  .pagination-btn {
    min-width: 3.75rem;
    padding: 0 0.5rem;
  }
  
  .pagination-info {
    font-size: 0.75rem;
  }
  
  .back-button {
    width: 2rem;
    height: 2rem;
    margin-right: 0.5rem;
  }
  
  .page-title {
    font-size: 1.25rem;
  }
  
  .title-underline {
    width: 4rem;
  }
  
  .version-badge {
    font-size: 0.7rem;
    padding: 0.1rem 0.375rem;
  }
  
  .stats-badge {
    font-size: 0.7rem;
    padding: 0.1rem 0.25rem;
  }
}

.version-badge {
  background: linear-gradient(135deg, #1976d2, #64b5f6);
  color: white;
  padding: 0.125rem 0.5rem;
  border-radius: 0.375rem;
  font-weight: 600;
  font-size: 0.75rem;
  box-shadow: 0 1px 3px rgba(25, 118, 210, 0.3);
  letter-spacing: 0.5px;
  display: inline-block;
}

.stats-badges {
  display: flex;
  gap: 0.375rem;
}

.stats-badge {
  padding: 0.125rem 0.375rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.stats-badge.success {
  background-color: rgba(46, 125, 50, 0.1);
  color: #2e7d32;
}

.stats-badge.paused {
  background-color: rgba(255, 152, 0, 0.1);
  color: #f57c00;
  font-weight: bold;
}

.version-item {
  margin-bottom: 0;
}

.page-highlight {
  color: #1976d2;
  font-weight: 600;
  font-size: 0.875rem;
  margin: 0 0.125rem;
}

.page-total {
  color: #606266;
  font-weight: 600;
  font-size: 0.875rem;
  margin: 0 0.125rem;
}

.data-count {
  color: #1976d2;
  font-weight: 600;
  font-size: 0.875rem;
  margin: 0 0.125rem;
}

:deep(.el-button.is-circle) {
  border-radius: 50%;
  outline: none !important;
}

:deep(.el-button.is-circle:focus),
:deep(.el-button.is-circle:focus-visible) {
  outline: none !important;
  box-shadow: none !important;
}

:deep(.el-button--primary) {
  background-color: #1890ff;
  border-color: #1890ff;
}

:deep(.el-button--primary:hover) {
  background-color: #40a9ff;
  border-color: #40a9ff;
}

:deep(.el-tag--dark.el-tag--danger) {
  background-color: #d32f2f;
  border-color: #d32f2f;
}

.import-dialog :deep(.el-dialog) {
  border-radius: 8px;
  overflow: hidden;
}

.import-dialog :deep(.el-dialog__header) {
  margin: 0;
  padding: 10px 16px;
  border-bottom: 1px solid #ebeef5;
  background-color: #fff;
}

.import-dialog :deep(.el-dialog__title) {
  font-weight: 600;
  font-size: 15px;
  color: #333;
}

.import-dialog :deep(.el-dialog__headerbtn) {
  top: 10px;
  right: 14px;
}

.import-dialog :deep(.el-dialog__body) {
  padding: 12px 16px 0;
}

.import-dialog :deep(.el-dialog__footer) {
  display: none;
}

.compact-form {
  padding: 0;
}

.form-row {
  margin-bottom: 16px;
}

.form-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  line-height: 1.1;
}

.form-label.required::before {
  content: "*";
  color: #f56c6c;
  margin-right: 4px;
}

.radio-container {
  display: flex;
  align-items: center;
  height: 32px;
  margin-top: 4px;
}

.dialog-divider {
  height: 1px;
  background-color: #ebeef5;
  margin: 16px -16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 0 4px;
}

.import-dialog :deep(.el-input__wrapper) {
  border-radius: 4px;
  height: 32px;
  line-height: 32px;
  box-shadow: 0 0 0 1px #dcdfe6 inset;
}

.import-dialog :deep(.el-input__inner) {
  height: 32px;
  line-height: 32px;
  font-size: 13px;
}

.import-dialog :deep(.el-radio) {
  margin-right: 24px;
  font-size: 13px;
  line-height: 32px;
  height: 32px;
}

.import-dialog :deep(.el-button) {
  height: 32px;
  padding: 6px 12px;
  font-size: 13px;
}

.file-upload-container {
  display: flex;
  gap: 8px;
  margin-bottom: 0;
  flex-wrap: nowrap;
  position: relative;
  align-items: center;
}

.file-upload-container .el-input {
  flex: 1;
}

.file-upload-container .el-button {
  flex-shrink: 0;
  min-width: 80px;
  height: 32px;
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 13px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.2;
  text-align: right;
  position: absolute;
  right: 0;
  top: 36px;
}

.record-status {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.125rem 0;
}

.info-icon {
  margin-right: 0.5rem;
  color: #1976d2;
  font-size: 1rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.5rem;
  height: 3.125rem;
}

.header-with-back {
  display: flex;
  align-items: center;
  width: 100%;
  position: relative;
}

.back-button {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  background-color: #f0f7ff;
  color: #1976d2;
  transition: all 0.3s ease;
  box-shadow: 0 2px 6px rgba(25, 118, 210, 0.2);
  border: 1px solid #e6f0fd;
  margin-right: 0.75rem;
}

.back-button:hover {
  background-color: #e3f2fd;
  transform: translateX(-3px);
  box-shadow: 0 3px 8px rgba(25, 118, 210, 0.25);
}

.back-icon {
  font-size: 1.125rem;
  color: #1976d2;
}

.page-title-container {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  padding-bottom: 0.375rem;
  text-align: center;
}

.page-title {
  font-size: 1.375rem;
  font-weight: 600;
  margin: 0;
  color: #1565c0;
  display: inline-block;
}

.title-underline {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 5rem;
  height: 3px;
  background: linear-gradient(90deg, #1976d2, #64b5f6);
  border-radius: 3px;
}

@media (max-width: 576px) {
  .back-button {
    width: 2rem;
    height: 2rem;
    margin-right: 0.5rem;
  }
  
  .page-title {
    font-size: 1.25rem;
  }
  
  .title-underline {
    width: 4rem;
  }
  
  .version-badge {
    font-size: 0.7rem;
    padding: 0.1rem 0.375rem;
  }
  
  .stats-badge {
    font-size: 0.7rem;
    padding: 0.1rem 0.25rem;
  }
}

.el-row {
  margin-left: -12px !important;
  margin-right: -12px !important;
}

.el-col {
  padding-left: 12px !important;
  padding-right: 12px !important;
}

.result-badge {
  position: absolute;
  right: 0;
  top: 40px;
  display: flex;
  align-items: center;
  padding: 4px 8px 4px 12px;
  border-radius: 20px 0 0 20px;
  color: #ffffff;
  font-weight: 600;
  font-size: 0.85rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 5;
  transition: all 0.3s ease;
}

.result-badge.result-success {
  background: linear-gradient(135deg, #2e7d32, #4caf50);
}

.result-badge.result-failed {
  background: linear-gradient(135deg, #d32f2f, #f44336);
}

.result-icon {
  margin-right: 4px;
  font-size: 14px;
}

.result-text {
  letter-spacing: 1px;
}

.record-card:hover .result-badge {
  padding-right: 12px;
  transform: translateX(-3px);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.2);
}

@media (max-width: 576px) {
  .result-badge {
    padding: 3px 6px 3px 10px;
    font-size: 0.75rem;
    top: 40px;
  }
  
  .result-icon {
    font-size: 12px;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: #909399;
  font-size: 1.125rem;
  text-align: center;
  height: 100%;
  min-height: 300px;
}

.empty-icon {
  margin-bottom: 1.5rem;
  color: #dcdfe6;
}

.empty-text {
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #606266;
  font-size: 1.25rem;
}

.empty-subtext {
  font-size: 0.875rem;
  color: #909399;
}

@media (max-width: 576px) {
  .empty-state {
    padding: 2rem 1rem;
    min-height: 200px;
  }
  
  .empty-icon svg {
    width: 60px;
    height: 60px;
  }
  
  .empty-text {
    font-size: 1.125rem;
  }
}
</style>
