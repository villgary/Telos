import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Vitest's default include matches **/*.{test,spec}.?(c|m)[jt]s?(x),
    // which scoops up e2e/*.spec.ts. Those are Playwright specs —
    // when Vitest's transform runs them, the Playwright `test()` wrapper
    // throws "did not expect test() to be called here". Restrict include
    // to src/ so each runner only sees its own files.
    include: ['src/**/*.{test,spec}.?(c|m)[jt]s?(x)'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
})