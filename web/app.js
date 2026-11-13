import {GrabGesture,EasySwipe} from './gesture.js';
const $=id=>document.getElementById(id);
const page=$('page'),stage=$('stage'),video=$('video'),art=$('art');
let images=[],index=0,urls=[],gesture=new GrabGesture(),running=false,starting=false,worker=null;
let stream=null,busy=false,lastVideoTime=-1,animation=null,session=0,frameCount=0,lastResult=0;
let trackingTimer=null,lastPoint=null,pointer=null,turning=false,turnTimer=null;
const skeleton=$('skeleton'),ctx=skeleton.getContext('2d');
const message=(text,error=false)=>{ $('message').textContent=text;$('message').classList.toggle('error',error); };
const connections=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
function drawHand(hand,gripped=false) {
  ctx.clearRect(0,0,160,100);
  if(!hand) {
    ctx.fillStyle='#9b9284';ctx.font='11px sans-serif';ctx.textAlign='center';
    ctx.fillText('ここに手の骨格を表示',80,55);return;
  }
  ctx.strokeStyle=gripped?'#bc8351':'#286957';ctx.lineWidth=2;
  for(const[a,b]of connections){ctx.beginPath();ctx.moveTo(hand[a].x*160,hand[a].y*100);ctx.lineTo(hand[b].x*160,hand[b].y*100);ctx.stroke();}
  ctx.fillStyle='#286957';for(const p of hand){ctx.beginPath();ctx.arc(p.x*160,p.y*100,2.1,0,Math.PI*2);ctx.fill();}
}
function resetPage() {
  page.classList.remove('grabbed');page.classList.add('settling');
  page.style.removeProperty('--drag');page.style.removeProperty('--rotate');page.style.removeProperty('--tilt');page.style.opacity='';
}
function dragPage(delta,grabbed) {
  if(turning)return;
  page.classList.remove('settling');page.classList.toggle('grabbed',!!grabbed);
  const px=delta*stage.clientWidth*.95;
  page.style.setProperty('--drag',`${px}px`);
  page.style.setProperty('--rotate',`${-delta*22}deg`);
  page.style.setProperty('--tilt',`${delta*6}deg`);
  $('drag-hint').textContent=grabbed?'そのまま横に動かして、手を開くとめくれます':'マウスでも、ページをつかんでめくれます';
  const target=(index+(delta>0?-1:1)+images.length)%images.length;
  if(images.length)$('under-image').src=images[target].url;
}
function render() {
  const item=images[index];
  $('empty').hidden=!!item;
  $('empty').style.display=item?'none':'flex';
  art.hidden=!item;
  if(item){art.src=item.url;art.alt=item.title;$('title').textContent=item.title;}
  else {art.removeAttribute('src');$('title').textContent='画像を選んでください';}
  $('count').textContent=item?`${String(index+1).padStart(3,'0')} / ${String(images.length).padStart(3,'0')}`:'画像未選択';
  $('previous').disabled=$('next').disabled=images.length<2;
  $('camera').disabled=!images.length || starting;
  if(item)$('under-image').src=images[(index+1)%images.length].url;
}
function turn(direction) {
  if(turning)return;
  if(images.length<2){resetPage();return;}
  turning=true;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  page.classList.remove('grabbed');page.classList.add('settling');
  page.style.setProperty('--drag',`${-direction*stage.clientWidth*.9}px`);
  page.style.setProperty('--rotate',`${direction*15}deg`);page.style.opacity='0';
  turnTimer=setTimeout(()=>{
    index=(index+direction+images.length)%images.length;render();
    page.classList.remove('settling');page.style.transition='none';resetPage();
    // Restore transition after resetting the incoming sheet without a reverse animation.
    void page.offsetWidth;page.style.transition='';turning=false;turnTimer=null;
  },reduced?0:260);
}
function setImages(items) {
  clearTimeout(turnTimer);turning=false;turnTimer=null;resetPage();
  for(const url of urls)URL.revokeObjectURL(url);urls=[];
  images=items;index=0;gesture.reset();render();
}
function configureGesture(){gesture.reset();gesture=$('mode').value==='grab'?new GrabGesture({distance:+$('sensitivity').value}):new EasySwipe({distance:+$('sensitivity').value});resetPage();
  $('step').textContent=$('mode').value==='grab'?'つかんでめくる':'軽いスワイプ';
  document.querySelector('.steps').hidden=$('mode').value!=='grab';
  message($('mode').value==='grab'?'手を開く → つかむ → 横へ動かして離す':'開いた手を横へ軽く動かすと、作品が切り替わります');}
function processLandmarks(hand,now) {
  const result=gesture.update(hand,now);drawHand(hand,result.grabbed);lastPoint=result.point;
  if(!pointer){if(result.page)turn(result.page);else if(result.released || result.cancel)resetPage();else dragPage(result.drag||0,result.grabbed);}
  message(result.message);
  const cursor=$('hand-cursor');cursor.classList.toggle('visible',!!result.point);
  if(result.point){cursor.style.left=`${result.point.x*100}%`;cursor.style.top=`${Math.max(.12,Math.min(.85,result.point.y))*100}%`;cursor.querySelector('span').textContent=result.grabbed?'✊':'✋';}
  return result;
}
async function cameraList(){try{const devices=await navigator.mediaDevices.enumerateDevices();const selected=$('camera-device').value;
  $('camera-device').replaceChildren(new Option('標準のカメラ',''));
  for(const d of devices.filter(d=>d.kind==='videoinput'))$('camera-device').add(new Option(d.label||'カメラ',d.deviceId));
  if([...$('camera-device').options].some(o=>o.value===selected))$('camera-device').value=selected;
}catch{/* The browser may hide device labels before camera permission is granted. */}}
function stopCamera(text='カメラを停止しました。マウスや矢印キーでもめくれます。') {
  session++;running=starting=false;busy=false;cancelAnimationFrame(animation);clearInterval(trackingTimer);
  worker?.terminate();worker=null;stream?.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;
  gesture.reset();resetPage();drawHand(null);$('hand-cursor').classList.remove('visible');
  $('camera-state').textContent='カメラ停止中';$('camera').textContent='カメラを使う';$('camera').classList.remove('running');
  $('camera-device').disabled=false;render();message(text);
}
async function startCamera(){
  if(starting || running)return;
  if(!navigator.mediaDevices?.getUserMedia){message('カメラは localhost または HTTPS で開いてください。',true);return;}
  const id=++session;starting=true;render();$('camera').textContent='カメラを準備中…';message('カメラの利用を許可してください。');
  try{
    const device=$('camera-device').value;
    const pending=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},...(device?{deviceId:{exact:device}}:{facingMode:'user'})},audio:false});
    if(id!==session){pending.getTracks().forEach(t=>t.stop());return;}
    stream=pending;video.srcObject=stream;await video.play();if(id!==session)return;
    await cameraList();if(id!==session)return;
    message('手の認識を準備しています…');
    const tracker=new Worker('/tracking-worker.js');worker=tracker;
    tracker.onerror=event=>{if(id===session){stopCamera();message(`認識処理を開始できません: ${event.message}`,true);}};
    tracker.onmessage=({data})=>{
      if(id!==session)return;
      if(data.type==='ready'){
        running=true;starting=false;lastResult=performance.now();lastVideoTime=-1;
        $('camera').textContent='カメラ停止';$('camera').classList.add('running');$('camera-device').disabled=true;
        $('camera-state').textContent='認識中';render();loop(id);
        trackingTimer=setInterval(()=>{if(running && performance.now()-lastResult>1200){gesture.reset();resetPage();drawHand(null);$('hand-cursor').classList.remove('visible');message('映像を待っています。カメラに手を向けてください。');}},300);
      } else if(data.type==='result'){
        busy=false;frameCount++;lastResult=performance.now();
        const hand=data.landmarks?.map(p=>({...p,x:1-p.x}));
        processLandmarks(hand,lastResult/1000);
      } else if(data.type==='error'){stopCamera();message(`手の認識を開始できません: ${data.message}`,true);}
    };
    tracker.postMessage({type:'init'});
    const timeoutSession=id;
    setTimeout(()=>{if(timeoutSession===session && starting){stopCamera();message('認識の準備がタイムアウトしました。再度開始してください。',true);}},30000);
  }catch(error){if(id!==session)return;stopCamera();message(error.name==='NotAllowedError'?'カメラが許可されていません。アドレスバーのサイト設定から許可してください。':`カメラを開けません: ${error.message}`,true);}
}
function loop(id){if(id!==session || !running)return;
  if(!busy && video.readyState>=2 && video.currentTime!==lastVideoTime){
    busy=true;lastVideoTime=video.currentTime;
    createImageBitmap(video).then(bitmap=>{if(id!==session || !worker){bitmap.close();return;}worker.postMessage({type:'frame',bitmap,timestamp:performance.now()},[bitmap]);}).catch(()=>{busy=false;});
  }
  animation=requestAnimationFrame(()=>loop(id));
}
$('camera').onclick=()=>running?stopCamera():startCamera();
$('previous').onclick=()=>{gesture.reset();turn(-1);};$('next').onclick=()=>{gesture.reset();turn(1);};
$('mode').onchange=$('sensitivity').onchange=configureGesture;
$('select-folder').onclick=$('empty-select').onclick=()=>{if(running||starting)stopCamera();$('files').click();};
$('files').onchange=event=>{
  const chosen=[...event.target.files].filter(f=>/\.(png|jpe?g|webp|gif|bmp)$/i.test(f.name)).sort((a,b)=>a.name.localeCompare(b.name,'ja',{numeric:true}));
  if(!chosen.length){message('PNG・JPEGなどの画像が入ったフォルダーを選んでください。',true);return;}
  setImages([]);
  urls=chosen.map(file=>URL.createObjectURL(file));images=chosen.map((file,i)=>({url:urls[i],title:file.name.replace(/\.[^.]+$/,'')}));index=0;render();message(`${images.length}枚の作品を読み込みました。`);
};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{message('全画面にするにはブラウザーの F11 を使ってください。');}};
page.addEventListener('pointerdown',event=>{if(event.button!==0 || !images.length || turning || event.target.closest('button'))return;pointer={id:event.pointerId,start:event.clientX,dx:0};gesture.reset();page.setPointerCapture(event.pointerId);dragPage(0,true);});
page.addEventListener('pointermove',event=>{if(!pointer||event.pointerId!==pointer.id)return;pointer.dx=(event.clientX-pointer.start)/stage.clientWidth;dragPage(pointer.dx,true);});
function releasePointer(event,cancel=false){if(!pointer||event.pointerId!==pointer.id)return;const delta=pointer.dx;pointer=null;gesture.reset();if(!cancel && Math.abs(delta)>=+ $('sensitivity').value)turn(delta<0?1:-1);else resetPage();}
page.addEventListener('pointerup',e=>releasePointer(e));page.addEventListener('pointercancel',e=>releasePointer(e,true));
window.addEventListener('keydown',event=>{if(event.target.matches('input,select,summary,button') && event.key!=='Escape')return;
  if(event.key==='ArrowRight'){event.preventDefault();gesture.reset();turn(1);}if(event.key==='ArrowLeft'){event.preventDefault();gesture.reset();turn(-1);}if(event.key==='Escape')stopCamera();});
document.addEventListener('visibilitychange',()=>{if(document.hidden && (running||starting))stopCamera('展示画面から離れたため、カメラを停止しました。');});
window.addEventListener('pagehide',()=>stopCamera());
art.onerror=()=>message('この画像を表示できませんでした。矢印ボタンで次の作品へ進めます。',true);
drawHand(null);render();
try{const response=await fetch('/api/images');if(!response.ok)throw Error('画像一覧を取得できません');const data=await response.json();setImages(data.images||[]);}catch{message('画像フォルダーを選んで、展示を始めてください。');}
// Read-only diagnostics and a development-only landmark replay for integration tests.
Object.defineProperty(window,'galleryState',{get:()=>({index,count:images.length,running,starting,frameCount,grabbed:gesture.grabbed||false})});
if(new URLSearchParams(location.search).has('test'))window.galleryReplay=(hand,now)=>processLandmarks(hand,now);
