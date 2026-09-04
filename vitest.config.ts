import { defineConfig } from 'vitest/config'
import { resolve } from 'path'

export default defineConfig({
  test: {
    globals: true, exclude: ['**/node_modules/**', '**/dist/**', '**/.next/**', '**/.git/**', '**/.cache/**', '__tests__/setup-agent.test.js'],
    environment: 'node',
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, '.'),
    },
  },
})
