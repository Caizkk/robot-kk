import { app, BrowserWindow, ipcMain, screen, shell, session } from 'electron'
import path from 'path'
import os from 'os'
import fs from 'fs'
import { spawn, spawnSync, ChildProcess } from 'child_process'
// 使用 any 类型导入 electron-log
// @ts-ignore
import log from 'electron-log'

// 配置日志
log.initialize({ preload: true })
log.transports.file.resolvePathFn = () => path.join(app.getPath('userData'), 'logs/main.log')
log.transports.file.level = 'info'
log.transports.console.level = 'debug'

// 日志文件大小限制为 10MB
log.transports.file.maxSize = 10 * 1024 * 1024
// 保留最近5个日志文件
log.transports.file.archiveLog = (oldLogFile: string) => {
  const info = path.parse(oldLogFile)
  return path.join(info.dir, `${info.name}.old.${Date.now()}${info.ext}`)
}

// 添加DPI感知设置
app.commandLine.appendSwitch('high-dpi-support', '1')

// 设置应用根目录
process.env.APP_ROOT = path.join(__dirname, '..')

// 导出路径常量
export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron')
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist')
process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, 'public') : RENDERER_DIST

// 全局变量
let win: BrowserWindow | null
let currentScaleFactor: number = 0
let currentScreenWidth: number = 0
let currentScreenHeight: number = 0
let scaleFactorHistory: number[] = []
let pythonProcess: ChildProcess | null = null

// 禁用Chromium的默认焦点样式
app.commandLine.appendSwitch('disable-features', 'FocusMode,PointerLock')

// 单实例锁定
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  // 配置CSP
  app.whenReady().then(() => {
    session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          'Content-Security-Policy': [
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://localhost:8111 http://127.0.0.1:8111 ws://localhost:5173; img-src 'self' data:; font-src 'self' data:;"
          ]
        }
      });
    });
  });

  // 监听第二个实例的启动
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  // 处理系统信息请求
  ipcMain.handle('get-system-info', () => {
    return {
      platform: os.platform(),
      arch: os.arch(),
      cpus: os.cpus().length,
      memory: {
        total: os.totalmem(),
        free: os.freemem()
      },
      hostname: os.hostname(),
      userInfo: os.userInfo().username
    }
  })

  // 窗口控制事件处理
  ipcMain.on('window-minimize', () => {
    if (win) win.minimize()
  })

  ipcMain.on('window-close', () => {
    // 先停止Python进程，然后关闭窗口
    stopPythonProcess()
    if (win) win.close()
  })

  ipcMain.on('window-show', () => {
    if (win) {
      win.show()
      win.focus()
      
      // 短暂置顶，然后恢复正常
      win.setAlwaysOnTop(true)
      setTimeout(() => {
        if (win) win.setAlwaysOnTop(false)
      }, 200)
    }
  })

  // 监听屏幕缩放因子和分辨率变化
  function setupScreenDetection() {
    // 获取初始屏幕信息
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize
    currentScaleFactor = primaryDisplay.scaleFactor
    currentScreenWidth = width
    currentScreenHeight = height
    
    // 初始化缩放因子历史记录
    scaleFactorHistory = [currentScaleFactor]
    
    // 监听显示器变化事件
    screen.on('display-metrics-changed', (_, display, __) => {
      if (display.id === primaryDisplay.id) {
        const newScaleFactor = display.scaleFactor
        const { width: newWidth, height: newHeight } = display.workAreaSize
        const scaleChanged = Math.abs(newScaleFactor - currentScaleFactor) > 0.01
        const resolutionChanged = newWidth !== currentScreenWidth || newHeight !== currentScreenHeight
        
        // 记录缩放因子历史
        if (scaleChanged) {
          scaleFactorHistory.push(newScaleFactor)
          // 只保留最近5个记录
          if (scaleFactorHistory.length > 5) {
            scaleFactorHistory.shift()
          }
        }
        
        if (scaleChanged || resolutionChanged) {
          // 更新当前值
          currentScaleFactor = newScaleFactor
          currentScreenWidth = newWidth
          currentScreenHeight = newHeight
          
          // 通知渲染进程屏幕变化了
          if (win) {
            win.webContents.send('screen-changed', {
              scaleFactor: newScaleFactor,
              width: newWidth,
              height: newHeight,
              scaleChanged,
              resolutionChanged,
              scaleFactorHistory: [...scaleFactorHistory]
            })
            
            // 重新计算窗口大小和位置
            updateWindowSizeAndPosition(win, newWidth, newHeight, newScaleFactor)
          }
        }
      }
    })
  }

  // 提取窗口大小和位置计算逻辑到单独的函数
  function calculateWindowSizeAndPosition(screenWidth: number, screenHeight: number, _: number) {
    // 计算窗口高度 - 固定为屏幕高度的70%
    const heightRatio = 0.7
    const windowHeight = Math.floor(screenHeight * heightRatio)
    
    // 计算窗口宽度（宽高比为4.3:8）
    const aspectRatio = 4.4 / 8
    const windowWidth = Math.floor(windowHeight * aspectRatio)
    
    // 确保窗口显示在右下角
    const x = Math.floor(screenWidth - windowWidth)
    const y = Math.floor(screenHeight - windowHeight)
    
    return { width: windowWidth, height: windowHeight, x, y }
  }

  // 更新窗口大小和位置
  function updateWindowSizeAndPosition(window: BrowserWindow, screenWidth: number, screenHeight: number, scaleFactor: number) {
    const { width: windowWidth, height: windowHeight, x, y } = calculateWindowSizeAndPosition(screenWidth, screenHeight, scaleFactor)
    
    // 重新设置窗口大小和位置
    window.setBounds({
      width: windowWidth,
      height: windowHeight,
      x: x,
      y: y
    }, true) // true表示动画过渡
    
    // 强制刷新窗口内容
    setTimeout(() => {
      if (window) {
        window.reload()
      }
    }, 300)
  }

  // 添加获取当前缩放因子的方法
  ipcMain.handle('get-scale-factor', (_) => {
    const primaryDisplay = screen.getPrimaryDisplay()
    return primaryDisplay.scaleFactor
  })

  // 添加获取当前屏幕信息的方法
  ipcMain.handle('get-screen-info', (_) => {
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize
    return {
      scaleFactor: primaryDisplay.scaleFactor,
      width,
      height,
      scaleFactorHistory: [...scaleFactorHistory]
    }
  })

  // 启动Python程序
  function startPythonProcess() {
    try {
      // 使用嵌入式Python解释器
      const pythonPath = path.join(process.env.APP_ROOT, '..', 'intelligent-robot', 'python', 'python-3.8.10-embed-amd64', 'python.exe')
      const scriptPath = path.join(process.env.APP_ROOT, '..', 'intelligent-robot', 'main.py')
      
      // 检查文件是否存在
      if (!fs.existsSync(pythonPath)) {
        console.error(`Python解释器不存在: ${pythonPath}`)
        return Promise.resolve(false)
      }
      
      if (!fs.existsSync(scriptPath)) {
        console.error(`Python脚本不存在: ${scriptPath}`)
        return Promise.resolve(false)
      }

      // 获取intelligent-robot目录的绝对路径
      const robotDirPath = path.join(process.env.APP_ROOT, '..', 'intelligent-robot')
      
      // 先运行命令设置控制台编码为UTF-8
      try {
        if (process.platform === 'win32') {
          // 在Windows上运行chcp 65001命令设置控制台编码为UTF-8
          const chcpProcess = spawn('chcp', ['65001'], { shell: true })
          chcpProcess.on('close', (code) => {
            log.info(`设置控制台编码命令退出，退出码: ${code}`)
          })
        }
      } catch (err) {
        log.error(`设置控制台编码失败: ${err}`)
      }
      
      // 直接启动主程序
      return startMainPythonProcess(pythonPath, scriptPath)
    } catch (error) {
      log.error('启动Python进程失败:', error)
      return Promise.resolve(false)
    }
  }

  // 启动主Python程序
  async function startMainPythonProcess(pythonPath: string, scriptPath: string): Promise<boolean> {
    try {
      // 设置启动超时
      const startTimeout = 30000 // 30秒超时
      let startTimer: NodeJS.Timeout | null = null
      
      // 获取intelligent-robot目录的绝对路径
      const robotDirPath = path.join(process.env.APP_ROOT, '..', 'intelligent-robot')
      
      // 创建一个.pth文件来修复Python路径问题
      try {
        const pythonDir = path.join(robotDirPath, 'python', 'python-3.8.10-embed-amd64')
        const pthFile = path.join(pythonDir, 'python38._pth')
        
        // 确保site模块被导入
        let pthContent = fs.readFileSync(pthFile, 'utf8')
        if (!pthContent.includes('import site')) {
          pthContent += '\nimport site'
          fs.writeFileSync(pthFile, pthContent)
          log.info('已添加site模块导入到python38._pth')
        }
      } catch (err) {
        log.error(`修改.pth文件失败: ${err}`)
      }
      
      // 启动Python进程
      pythonProcess = spawn(pythonPath, [scriptPath], {
        // 使用shell在Windows上可以更好地处理路径问题
        shell: process.platform === 'win32',
        // 改为pipe以便我们可以读取输出
        stdio: 'pipe',
        // 设置工作目录为intelligent-robot目录
        cwd: robotDirPath,
        // 合并环境变量
        env: {
          ...process.env,
          // 可以在这里添加额外的环境变量
          PYTHONIOENCODING: 'utf-8', // 确保Python输出使用UTF-8编码
          PYTHONPATH: `${robotDirPath};${path.join(robotDirPath, 'app')}`, // 设置Python模块搜索路径
          PYTHONHOME: path.join(robotDirPath, 'python', 'python-3.8.10-embed-amd64'), // 设置Python主目录
          PYTHONDONTWRITEBYTECODE: '1', // 不生成.pyc文件
        }
      })
      
      // 设置初始超时
      startTimer = setTimeout(() => {
        if (pythonProcess) {
          // 注意：这里我们不终止进程，只是标记超时
        }
      }, startTimeout)
      
      // 处理Python进程的输出
      if (pythonProcess.stdout) {
        pythonProcess.stdout.on('data', (data) => {
          try {
            const output = data.toString('utf8').trim()
            if (output) {
              // 直接输出Python的标准输出，不添加前缀
              log.info(output)
              
              // 如果收到输出，并且包含服务器启动成功的信息，清除超时
              if (output.includes('Application startup complete') || 
                  output.includes('Uvicorn running on') || 
                  output.includes('应用初始化完成')) {
                if (startTimer) {
                  clearTimeout(startTimer)
                  startTimer = null
                }
              }
            }
          } catch (e) {
            log.error(`处理输出时出错: ${e}`)
          }
        })
      }
      
      if (pythonProcess.stderr) {
        pythonProcess.stderr.on('data', (data) => {
          try {
            const output = data.toString('utf8').trim()
            if (output) {
              // 检查输出内容，判断是否为真正的错误
              const lines = output.split('\n')
              for (const line of lines) {
                if (line.trim()) {
                  // 检查是否包含常见的错误关键词
                  const isError = line.toLowerCase().includes('error') || 
                                 line.toLowerCase().includes('exception') ||
                                 line.toLowerCase().includes('traceback') ||
                                 line.toLowerCase().includes('failed') ||
                                 line.toLowerCase().includes('critical')
                  
                  // 检查是否包含INFO级别的日志
                  const isInfo = line.toLowerCase().includes('info:') ||
                                line.toLowerCase().includes(' - ') && 
                                (line.includes('INFO') || line.includes('WARNING') || line.includes('DEBUG'))
                  
                  // 检查是否包含警告关键词
                  const isWarning = line.toLowerCase().includes('warning') ||
                                   line.toLowerCase().includes('deprecated')
                  
                  if (isError) {
                    log.error(line)
                  } else if (isWarning) {
                    log.warn(line)
                  } else if (isInfo || line.includes(' - ')) {
                    // 对于包含时间戳和日志级别的行，按INFO处理
                    log.info(line)
                  } else {
                    // 默认按INFO处理，因为Python的日志可能通过stderr输出
                    log.info(line)
                  }
                }
              }
            }
          } catch (e) {
            log.error(`处理错误输出时出错: ${e}`)
          }
        })
      }
      
      return new Promise((resolve) => {
        // 添加错误处理
        pythonProcess?.on('error', (err) => {
          if (startTimer) clearTimeout(startTimer)
          log.error(`启动Python进程时出错: ${err.message}`)
          pythonProcess = null
          resolve(false)
        })
        
        // 检测进程是否立即退出
        pythonProcess?.on('exit', (code, signal) => {
          if (startTimer) clearTimeout(startTimer)
          if (code !== null) {
            log.error(`Python进程立即退出，退出码: ${code}`)
            pythonProcess = null
            resolve(false)
          } else if (signal) {
            log.error(`Python进程被信号终止: ${signal}`)
            pythonProcess = null
            resolve(false)
          }
        })
        
        // 给进程一点时间启动
        setTimeout(() => {
          // 如果进程还在运行，我们认为启动成功
          if (pythonProcess && pythonProcess.pid) {
            log.info(`Python进程启动成功`)
            
            // 继续监听进程关闭事件
            pythonProcess.on('close', () => {
              pythonProcess = null
            })
            
            resolve(true)
          } else {
            log.error('Python进程启动失败')
            resolve(false)
          }
        }, 2000) // 等待2秒检查进程是否还活着
      })
    } catch (err) {
      log.error(`无法启动Python进程: ${err}`)
      return false
    }
  }
  
  // 停止Python进程
  function stopPythonProcess() {
    if (pythonProcess) {
      // 停止Python进程
      try {
        if (process.platform === 'win32') {
          // Windows下使用taskkill强制结束进程树
          if (pythonProcess.pid) {
            // 使用同步方式确保进程被终止
            spawnSync('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t'])
            
            // 再次检查进程是否还在运行
            try {
              const checkResult = spawnSync('tasklist', ['/fi', `pid eq ${pythonProcess.pid}`], { encoding: 'utf8' })
              if (checkResult.stdout.includes(pythonProcess.pid.toString())) {
                // 进程仍在运行，再次终止
                spawnSync('taskkill', ['/pid', pythonProcess.pid.toString(), '/f'], { timeout: 5000 })
              }
            } catch (e) {
              // 忽略错误
            }
          }
        } else {
          // Linux/Mac下发送SIGTERM信号
          pythonProcess.kill('SIGTERM')
          
          // 给进程一点时间来优雅地退出
          setTimeout(() => {
            // 如果进程还在运行，发送SIGKILL信号强制终止
            try {
              if (pythonProcess && !pythonProcess.killed) {
                pythonProcess.kill('SIGKILL')
              }
            } catch (e) {
              // 忽略错误
            }
          }, 2000)
        }
      } catch (err) {
        // 忽略错误
      } finally {
        pythonProcess = null
      }
    }
  }

  function createWindow() {
    // 获取屏幕尺寸
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize
    const scaleFactor = primaryDisplay.scaleFactor
    
    // 保存初始屏幕信息
    currentScaleFactor = scaleFactor
    currentScreenWidth = width
    currentScreenHeight = height
    // 初始化缩放因子历史
    scaleFactorHistory = [scaleFactor]
    
    // 计算窗口大小和位置
    const { width: windowWidth, height: windowHeight, x, y } = calculateWindowSizeAndPosition(width, height, scaleFactor)

    win = new BrowserWindow({
      title: '和元智擎机器人',
      width: windowWidth,
      height: windowHeight,
      x: x,
      y: y,
      resizable: false,
      movable: true,
      frame: false,
      autoHideMenuBar: true,
      icon: path.join(process.env.VITE_PUBLIC, 'logo.ico'),
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: false,
        additionalArguments: ['--disable-focus-outline'],
        zoomFactor: 1.0
      },
      maximizable: false,
      show: false, // 初始不显示，等ready-to-show事件后再显示
      focusable: true
    })

    // 隐藏菜单栏
    win.setMenuBarVisibility(false)

    // 在窗口创建完成后，确保它获得焦点但不一直置顶
    win.once('ready-to-show', () => {
      win?.show()
      win?.focus()
      
      // 短暂置顶以确保窗口可见，然后恢复正常
      win?.setAlwaysOnTop(true)
      setTimeout(() => {
        if (win) win.setAlwaysOnTop(false)
      }, 200)
    })

    win.webContents.on('did-finish-load', () => {
      win?.webContents.send('main-process-message', (new Date).toLocaleString())
    })

    if (VITE_DEV_SERVER_URL) {
      win.loadURL(VITE_DEV_SERVER_URL)
      win.webContents.openDevTools()
    } else {
      win.loadFile(path.join(RENDERER_DIST, 'index.html'))
    }
    
    // 设置缩放因子检测
    setupScreenDetection()
    
    // 添加窗口拖动事件处理
    ipcMain.on('window-drag', () => {
      if (win) {
        win.setMovable(true)
      }
    })
  }

  app.on('window-all-closed', () => {
    // 停止Python进程
    stopPythonProcess()
    
    if (process.platform !== 'darwin') {
      app.quit()
      win = null
    }
  })

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
      // 确保Python进程正在运行
      if (!pythonProcess) {
        await startPythonProcess()
      }
    }
  })

  app.whenReady().then(async () => {
    createWindow()
    // 启动Python进程，添加超时和重试机制
    try {
      log.info('开始启动Python进程...')
      // 设置总体超时
      const totalTimeout = 300000 // 5分钟
      const startTime = Date.now()
      
      // 尝试启动Python进程
      let success = await Promise.race([
        startPythonProcess(),
        new Promise<boolean>((resolve) => {
          setTimeout(() => {
            log.error('启动Python进程总体超时')
            resolve(false)
          }, totalTimeout)
        })
      ])
      
      // 如果启动失败，尝试重启一次
      if (!success && Date.now() - startTime < totalTimeout) {
        log.info('首次启动失败，尝试重新启动Python进程...')
        // 确保之前的进程已经停止
        stopPythonProcess()
        
        // 等待一段时间
        await new Promise(resolve => setTimeout(resolve, 3000))
        
        // 再次尝试启动
        success = await Promise.race([
          startPythonProcess(),
          new Promise<boolean>((resolve) => {
            setTimeout(() => {
              log.error('重启Python进程超时')
              resolve(false)
            }, totalTimeout - (Date.now() - startTime))
          })
        ])
      }
      
      if (!success) {
        log.error('无法启动Python进程，应用可能无法正常工作')
        // 通知渲染进程Python启动失败
        if (win) {
          win.webContents.on('did-finish-load', () => {
            win?.webContents.send('python-process-failed')
          })
        }
      } else {
        log.info('Python进程启动成功')
      }
    } catch (error) {
      log.error('启动Python进程时发生异常:', error)
    }
  })

  // 添加重新加载窗口的方法
  ipcMain.on('reload-window', () => {
    if (win) {
      // 获取当前主显示器
      const primaryDisplay = screen.getPrimaryDisplay()
      const { width, height } = primaryDisplay.workAreaSize
      const scaleFactor = primaryDisplay.scaleFactor
      
      // 更新当前值
      currentScaleFactor = scaleFactor
      currentScreenWidth = width
      currentScreenHeight = height
      
      // 记录缩放因子历史
      scaleFactorHistory.push(scaleFactor)
      if (scaleFactorHistory.length > 5) {
        scaleFactorHistory.shift()
      }
      
      // 重新计算窗口大小和位置
      updateWindowSizeAndPosition(win, width, height, scaleFactor)
    }
  })

  // 添加手动设置缩放因子的方法
  ipcMain.handle('set-zoom-factor', (_, zoomFactor) => {
    if (win && typeof zoomFactor === 'number' && zoomFactor > 0) {
      win.webContents.setZoomFactor(zoomFactor)
      return true
    }
    return false
  })

  // 添加获取当前缩放历史的方法
  ipcMain.handle('get-scale-factor-history', (_) => {
    return [...scaleFactorHistory]
  })

  // 处理打开本地日志文件请求
  ipcMain.handle('open-log-file', async (_, logPath) => {
    try {
      // 处理相对路径
      const absoluteLogPath = path.isAbsolute(logPath) 
        ? logPath 
        : path.join(process.env.APP_ROOT, '..', 'intelligent-robot', logPath)
        
      // 确保文件存在
      if (fs.existsSync(absoluteLogPath)) {
        // 使用系统默认应用打开文件
        await shell.openPath(absoluteLogPath)
        return { success: true, path: absoluteLogPath }
      } else {
        return { success: false, error: 'File not found', path: absoluteLogPath }
      }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })
  
  // 添加获取Python进程状态的方法
  ipcMain.handle('get-python-status', () => {
    return {
      running: pythonProcess !== null,
      pid: pythonProcess ? pythonProcess.pid : null
    }
  })
  
  // 添加获取日志文件路径的方法
  ipcMain.handle('get-log-path', () => {
    return {
      logFilePath: log.transports.file.getFile().path,
      logDirectory: path.dirname(log.transports.file.getFile().path)
    }
  })
  
  // 添加重启Python进程的方法
  ipcMain.handle('restart-python-process', async () => {
    try {
      // 先停止进程
      stopPythonProcess()
      
      // 等待一段时间确保进程完全停止
      return new Promise((resolve) => {
        setTimeout(async () => {
          try {
            // 重新启动进程
            const success = await startPythonProcess()
            resolve({ success })
          } catch (error) {
            resolve({ success: false, error: String(error) })
          }
        }, 1000)
      })
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })
}
