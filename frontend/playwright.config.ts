import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',timeout:120000,workers:1,use:{baseURL:process.env.PLAYWRIGHT_BASE_URL||'http://localhost:3000',headless:true,actionTimeout:15000,trace:'retain-on-failure'},reporter:[['list'],['json',{outputFile:'test-results/results.json'}]]});
