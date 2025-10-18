import { defineConfig } from 'vite'
import path from 'path'
import electron from 'vite-plugin-electron/simple'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
    electron({
      main: {
        entry: 'electron/main.ts',
        onstart({ startup }) {
          startup()
        },
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              output: {
                format: 'cjs',
              },
            },
          },
        },
      },
      preload: {
        input: path.join(__dirname, 'electron/preload.ts'),
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              output: {
                format: 'cjs',
              },
            },
          },
        },
      },
      renderer: process.env.NODE_ENV === 'test'
        ? undefined
        : {},
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8111',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
