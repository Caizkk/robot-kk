/// <reference types="vite-plugin-electron/electron-env" />

declare namespace NodeJS {
  interface ProcessEnv {
    APP_ROOT: string
    VITE_PUBLIC: string
  }
}

interface Window {
  ipcRenderer: import('electron').IpcRenderer
  electronAPI: {
    on: (...args: any[]) => any
    off: (...args: any[]) => any
    send: (...args: any[]) => any
    invoke: (...args: any[]) => any
    getAppInfo: () => {
      name: string
      version: string
      description: string
    }
    getSystemInfo: () => Promise<{
      platform: string
      arch: string
      cpus: number
      memory: {
        total: number
        free: number
      }
      hostname: string
      userInfo: string
    }>
    openLogFile: (logPath?: string) => Promise<{
      success: boolean
      path: string
      error?: string
    }>
    getDefaultLogPath: () => string
    windowControl: {
      minimize: () => void
      close: () => void
      drag: () => void
      show: () => void
    }
    screen: {
      getScaleFactor: () => Promise<number>
      getInfo: () => Promise<{
        scaleFactor: number
        width: number
        height: number
        scaleFactorHistory?: number[]
      }>
      reloadWindow: () => void
      onChanged: (callback: (screenInfo: {
        scaleFactor: number
        width: number
        height: number
        scaleChanged: boolean
        resolutionChanged: boolean
        scaleFactorHistory?: number[]
      }) => void) => void
      offChanged: () => void
      getScaleFactorHistory: () => Promise<number[]>
      setZoomFactor: (zoomFactor: number) => Promise<boolean>
      calculateOptimalZoom: (scaleFactor: number) => number
    }
    pythonProcess: {
      getStatus: () => Promise<{
        running: boolean
        pid: number | null
      }>
      restart: () => Promise<{
        success?: boolean
        restarting?: boolean
        error?: string
      }>
    }
  }
}
