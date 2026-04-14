import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60000, // 60s per test
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: 'http://192.168.1.9',
    actionTimeout: 15000,
  },
  launchOptions: {
    args: ['--no-proxy-server', '--disable-proxy-scraper'],
  },
  retries: 0,
  workers: 1, // Must run serially: login session is shared per browser context
})
