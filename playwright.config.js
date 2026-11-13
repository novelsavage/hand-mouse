import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'web/browser-tests',timeout:60000,workers:1,
  use:{baseURL:'http://localhost:8766',viewport:{width:1440,height:1000},
    launchOptions:{...(process.env.PLAYWRIGHT_USE_BUNDLED?{}:{executablePath:process.env.CHROME_BIN||'/usr/bin/google-chrome'}),args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']},
    permissions:['camera'],screenshot:'only-on-failure'},
  webServer:{command:'uv run python web_server.py --port 8766',url:'http://localhost:8766',reuseExistingServer:false}
});
