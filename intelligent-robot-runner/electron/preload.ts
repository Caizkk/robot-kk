import { ipcRenderer, contextBridge } from 'electron'
// @ts-ignore - 使用 any 类型导入 electron-log
import log from 'electron-log'

// 配置渲染进程日志
log.initialize({
  preload: true,
  // 在这里直接传入配置
  transports: {
    file: {
      fileName: 'renderer.log',
      level: 'info',
    },
    console: {
      level: 'debug',
    }
  }
})

// 默认日志文件路径
const DEFAULT_LOG_PATH = 'intelligent-robot/log/text.log'

// --------- 向渲染进程暴露API ---------
contextBridge.exposeInMainWorld('electronAPI', {
  on(...args: Parameters<typeof ipcRenderer.on>) {
    const [channel, listener] = args
    return ipcRenderer.on(channel, (event, ...args) => listener(event, ...args))
  },
  off(...args: Parameters<typeof ipcRenderer.off>) {
    const [channel, ...omit] = args
    return ipcRenderer.off(channel, ...omit)
  },
  send(...args: Parameters<typeof ipcRenderer.send>) {
    const [channel, ...omit] = args
    return ipcRenderer.send(channel, ...omit)
  },
  invoke(...args: Parameters<typeof ipcRenderer.invoke>) {
    const [channel, ...omit] = args
    return ipcRenderer.invoke(channel, ...omit)
  },

  // 应用信息API
  getAppInfo: () => {
    return {
      name: '和元智擎机器人',
      version: '1.0.0',
      description: '基于Electron、Vue3和Element Plus构建的现代化桌面应用'
    }
  },
  
  // 系统信息API
  getSystemInfo: () => {
    return ipcRenderer.invoke('get-system-info')
  },
  
  // 日志文件操作API
  openLogFile: (logPath: string = DEFAULT_LOG_PATH) => {
    return ipcRenderer.invoke('open-log-file', logPath)
  },
  
  getDefaultLogPath: () => {
    return DEFAULT_LOG_PATH
  },
  
  // 窗口控制API
  windowControl: {
    minimize: () => ipcRenderer.send('window-minimize'),
    close: () => ipcRenderer.send('window-close'),
    drag: () => ipcRenderer.send('window-drag'),
    show: () => ipcRenderer.send('window-show')
  },
  
  // 屏幕信息相关API
  screen: {
    // 获取当前缩放因子
    getScaleFactor: () => ipcRenderer.invoke('get-scale-factor'),
    
    // 获取屏幕信息
    getInfo: () => ipcRenderer.invoke('get-screen-info'),
    
    // 重新加载窗口
    reloadWindow: () => ipcRenderer.send('reload-window'),
    
    // 监听屏幕变化事件
    onChanged: (callback: (screenInfo: {
      scaleFactor: number,
      width: number,
      height: number,
      scaleChanged: boolean,
      resolutionChanged: boolean,
      scaleFactorHistory?: number[]
    }) => void) => {
      ipcRenderer.on('screen-changed', (_, screenInfo) => {
        callback(screenInfo)
      })
    },
    
    // 移除屏幕变化监听
    offChanged: () => {
      ipcRenderer.removeAllListeners('screen-changed')
    },
    
    // 获取缩放因子历史
    getScaleFactorHistory: () => ipcRenderer.invoke('get-scale-factor-history'),
    
    // 设置页面缩放因子
    setZoomFactor: (zoomFactor: number) => ipcRenderer.invoke('set-zoom-factor', zoomFactor),
    
    // 计算最佳缩放因子
    calculateOptimalZoom: (scaleFactor: number): number => {
      // 根据系统DPI缩放因子计算最佳的页面缩放值
      if (scaleFactor <= 1) return 1
      if (scaleFactor <= 1.5) return 1 - (scaleFactor - 1) * 0.3
      if (scaleFactor <= 2) return 0.85 - (scaleFactor - 1.5) * 0.2
      return 0.75 // 超高DPI
    }
  },
  
  // Python进程管理API
  pythonProcess: {
    // 获取Python进程状态
    getStatus: () => ipcRenderer.invoke('get-python-status'),
    
    // 重启Python进程
    restart: () => ipcRenderer.invoke('restart-python-process'),
    
    // 监听Python进程失败事件
    onFailed: (callback: () => void) => {
      ipcRenderer.on('python-process-failed', () => {
        callback()
      })
    },
    
    // 移除Python进程失败事件监听
    offFailed: () => {
      ipcRenderer.removeAllListeners('python-process-failed')
    }
  },
  
  // 日志API
  logger: {
    // 获取日志文件路径
    getLogPath: () => ipcRenderer.invoke('get-log-path'),
    
    // 日志级别方法
    info: (message: string, ...args: any[]) => log.info(message, ...args),
    warn: (message: string, ...args: any[]) => log.warn(message, ...args),
    error: (message: string, ...args: any[]) => log.error(message, ...args),
    debug: (message: string, ...args: any[]) => log.debug(message, ...args),
    
    // 打开日志文件目录
    openLogFile: () => {
      ipcRenderer.invoke('get-log-path').then((paths) => {
        ipcRenderer.invoke('open-log-file', paths.logFilePath)
      })
    },
    
    // 打开日志目录
    openLogDirectory: () => {
      ipcRenderer.invoke('get-log-path').then((paths) => {
        ipcRenderer.invoke('open-log-file', paths.logDirectory)
      })
    }
  }
})
