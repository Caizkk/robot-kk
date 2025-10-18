/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface Window {
  electronAPI: {
    on(channel: string, func: (...args: any[]) => void): void;
    off(channel: string, ...args: any[]): void;
    send(channel: string, ...args: any[]): void;
    invoke(channel: string, ...args: any[]): Promise<any>;
    getAppInfo(): any;
    getSystemInfo(): Promise<any>;
    openLogFile(logPath?: string): Promise<{success: boolean, error?: string, path?: string}>;
    getDefaultLogPath(): string;
    windowControl: {
      minimize(): void;
      close(): void;
      drag(): void;
    }
  }
}
