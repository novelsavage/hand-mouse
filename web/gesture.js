// Pure landmark state machine: no browser, camera, or DOM dependency.
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const dist = (a,b) => Math.hypot(a.x-b.x,a.y-b.y);
export function pose(hand, previousGrip=false) {
  if (!hand?.length || hand.length !== 21) return null;
  const palm=[0,5,9,13,17].map(i=>hand[i]);
  const x=palm.reduce((s,p)=>s+p.x,0)/5, y=palm.reduce((s,p)=>s+p.y,0)/5;
  const center={x,y};
  const curls=[[8,5],[12,9],[16,13],[20,17]].filter(([t,m])=>
    dist(hand[t],center)/Math.max(.001,dist(hand[m],center)) < (previousGrip?1.65:1.4)).length;
  const width=Math.max(.025,dist(hand[5],hand[17]));
  const pinch=dist(hand[4],hand[8])/width < (previousGrip ? .85 : .60);
  return {x,y,grip:curls>=2 || pinch,pinch};
}
export class GrabGesture {
  constructor({distance=.08}={}) { this.distance=distance; this.reset(); }
  reset() {
    this.ready=false; this.grabbed=false; this.anchor=null; this.dx=0;
    this.intentSince=null; this.releaseSince=null; this.lostSince=null; this.cooldownUntil=0;
  }
  update(hand,now) {
    const p=pose(hand,this.grabbed);
    const base={page:0,drag:this.dx,grabbed:this.grabbed,point:p};
    if (!p) {
      this.intentSince=null; this.releaseSince=null;
      if (this.lostSince===null) this.lostSince=now;
      if (now-this.lostSince>.3) {
        this.reset(); return {...base,drag:0,grabbed:false,cancel:true,message:'手をカメラに向けてください'};
      }
      return {...base,message:this.grabbed?'手を探しています…':'手を開いて、ページをつかんでみよう'};
    }
    this.lostSince=null;
    if (!this.grabbed) {
      if (!p.grip) { this.ready=true; this.intentSince=null; }
      if (p.grip && this.ready && now>=this.cooldownUntil) {
        if (this.intentSince===null) this.intentSince=now;
        if (now-this.intentSince>=.07) {
          this.grabbed=true; this.anchor=p.x; this.dx=0; this.releaseSince=null;
          return {...base,grabbed:true,drag:0,message:'つかめました。そのまま横に動かして、手を開こう'};
        }
      }
      return {...base,drag:0,grabbed:false,message:'手を握るか、親指と人差し指でつまんで、ページをつかもう'};
    }
    this.dx=clamp(p.x-this.anchor,-.7,.7);
    if (!p.grip) {
      if (this.releaseSince===null) this.releaseSince=now;
      if (now-this.releaseSince>=.10) {
        const page=Math.abs(this.dx)>=this.distance ? (this.dx<0?1:-1) : 0;
        this.grabbed=false; this.ready=true; this.anchor=null; this.dx=0;
        this.intentSince=null; this.releaseSince=null; this.cooldownUntil=now+.35;
        return {page,drag:0,grabbed:false,point:p,released:true,
          message:page?'めくれました。もう一度つかんでみよう':'もう少し横に動かしてから、手を開いてみよう'};
      }
    } else this.releaseSince=null;
    return {page:0,drag:this.dx,grabbed:true,point:p,
      message:Math.abs(this.dx)>=this.distance?'手を開くと、このページがめくれます':'つかんだまま、少し横へ動かそう'};
  }
}
export class EasySwipe {
  constructor({distance=.08}={}) {this.distance=distance;this.reset();}
  reset() {this.anchor=null;this.since=null;this.cooldownUntil=0;}
  update(hand,now) {
    const p=pose(hand);
    if(!p || p.grip) {this.anchor=null;this.since=null;return {page:0,drag:0,point:p,message:'開いた手を横へ軽く動かしてください'};}
    if(now<this.cooldownUntil) return {page:0,drag:0,point:p,message:'切り替えました。少し止めると、もう一度めくれます'};
    if(this.anchor===null) {this.anchor=p.x;this.since=now;}
    const dx=p.x-this.anchor;
    if(now-this.since>3) {this.anchor=p.x;this.since=now;}
    if(Math.abs(dx)>=this.distance) {
      const page=dx<0?1:-1;this.anchor=null;this.cooldownUntil=now+.7;
      return {page,drag:0,point:p,message:'切り替えました'};
    }
    return {page:0,drag:dx*.4,point:p,message:'左へ動かすと次の作品 / 右へ動かすと前の作品'};
  }
}
