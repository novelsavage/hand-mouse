// Render README screenshots using an illustrated fixture, never personal photos.
import {chromium} from '@playwright/test';
const browser=await chromium.launch({executablePath:process.env.CHROME_BIN||'/usr/bin/google-chrome'});
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720"><rect width="1200" height="720" fill="#dce8e3"/><circle cx="920" cy="155" r="68" fill="#e3b467"/><path d="M0 570 275 210 670 720H0" fill="#96b7ad"/><path d="m300 720 530-490 370 385v105" fill="#639083"/><path d="M0 610q550-180 1200-20v130H0" fill="#305e53"/><text x="35" y="50" font-family="sans-serif" font-size="22" fill="#305e53">SAMPLE / illustrated test image</text></svg>`;
await page.route('**/api/images',route=>route.fulfill({json:{images:[1,2,3].map(n=>({title:`サンプル作品 ${n}`,url:`/preview-${n}.svg`}))}}));
await page.route('**/preview-*.svg',route=>route.fulfill({contentType:'image/svg+xml',body:svg}));
await page.goto('http://localhost:8765');
await page.waitForFunction(()=>window.galleryState?.count===3);
await page.locator('#art').evaluate(img=>img.decode());
await page.screenshot({path:'docs/gallery-web.png',fullPage:true});
const box=await page.locator('#page').boundingBox();
await page.mouse.move(box.x+box.width*.6,box.y+box.height*.5);
await page.mouse.down();await page.mouse.move(box.x+box.width*.40,box.y+box.height*.5,{steps:10});
await page.screenshot({path:'docs/gallery-web-grab.png',fullPage:true});
await browser.close();
