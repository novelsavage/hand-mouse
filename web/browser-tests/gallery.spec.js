import {test,expect} from '@playwright/test';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
let sampleDir;
test.beforeAll(async()=>{sampleDir=await mkdtemp(join(tmpdir(),'hand-gallery-test-'));for(let i=1;i<=3;i++)await writeFile(join(sampleDir,`作品${i}.png`),png);});
test.afterAll(async()=>{if(sampleDir)await rm(sampleDir,{recursive:true,force:true});});
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4WQAAAAASUVORK5CYII=','base64');
function hand(x=.5,closed=false){const p=Array.from({length:21},()=>({x,y:.70}));for(const[m,mid,t,dx]of [[5,6,8,-.09],[9,10,12,-.03],[13,14,16,.03],[17,18,20,.09]]){p[m]={x:x+dx,y:.51};p[mid]={x:x+dx,y:.40};p[t]={x:x+dx,y:closed?.58:.25};}p[4]={x:x-.20,y:.5};return p;}
async function setup(page){
  await page.goto('/?test');await expect(page.locator('#message')).toBeVisible();
  await page.locator('#files').setInputFiles(sampleDir);
  await expect(page.locator('#count')).toHaveText('001 / 003');
}
test('buttons, keyboard and dragging the page change artwork',async({page})=>{
  await setup(page);await page.locator('#next').click();await expect(page.locator('#count')).toHaveText('002 / 003');
  await page.locator('#page').focus();await page.keyboard.press('ArrowLeft');await expect(page.locator('#count')).toHaveText('001 / 003');
  const box=await page.locator('#page').boundingBox();await page.mouse.move(box.x+box.width*.6,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.35,box.y+box.height*.5,{steps:10});
  await expect(page.locator('#page')).toHaveClass(/grabbed/);await page.mouse.up();await expect(page.locator('#count')).toHaveText('002 / 003');
});
test('landmark replay grabs and releases one page; losing a hand cancels',async({page})=>{
  await setup(page);
  const replay=async(h,t)=>page.evaluate(([hand,time])=>window.galleryReplay(hand,time),[h,t]);
  await replay(hand(.8),0);await replay(hand(.8,true),.1);await replay(hand(.8,true),.2);await expect(page.locator('#page')).toHaveClass(/grabbed/);
  await replay(hand(.68,true),2);await replay(hand(.68),2.2);await replay(hand(.68),2.4);await expect(page.locator('#count')).toHaveText('002 / 003');
  await replay(hand(.8),3);await replay(hand(.8,true),3.1);await replay(hand(.8,true),3.2);await replay(hand(.4,true),3.3);await replay(null,3.4);await replay(null,3.8);await expect(page.locator('#count')).toHaveText('002 / 003');
});
test('real MediaPipe worker initializes and processes camera frames; stop releases it',async({page})=>{
  await setup(page);await page.locator('#camera').click();
  await expect.poll(()=>page.evaluate(()=>window.galleryState.frameCount),{timeout:45000}).toBeGreaterThan(5);
  await expect(page.locator('#camera-state')).toHaveText('認識中');await page.locator('#camera').click();
  expect(await page.evaluate(()=>document.getElementById('video').srcObject)).toBeNull();
  await expect(page.locator('#camera-state')).toHaveText('カメラ停止中');
});
test('compact layout and sensitivity controls remain usable',async({page})=>{
  await setup(page);await page.setViewportSize({width:600,height:850});await page.locator('summary').click();
  await page.locator('#sensitivity').selectOption('.05');await page.locator('#mode').selectOption('swipe');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(page.locator('#select-folder')).toBeVisible();
});
