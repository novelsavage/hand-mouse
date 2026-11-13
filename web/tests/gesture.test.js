import test from 'node:test';
import assert from 'node:assert/strict';
import {GrabGesture,EasySwipe,pose} from '../gesture.js';
export function hand(x=.5,closed=false){
  const p=Array.from({length:21},()=>({x,y:.70}));
  for(const[m,mid,t,dx]of [[5,6,8,-.09],[9,10,12,-.03],[13,14,16,.03],[17,18,20,.09]]){
    p[m]={x:x+dx,y:.51};p[mid]={x:x+dx,y:.40};p[t]={x:x+dx,y:closed?.58:.25};
  }
  p[4]={x:x-.20,y:.50};return p;
}
function grab(g,x=.5,t=0){g.update(hand(x),t);g.update(hand(x,true),t+.1);assert.equal(g.update(hand(x,true),t+.2).grabbed,true);}
function release(g,x,t){g.update(hand(x),t);return g.update(hand(x),t+.12);}
test('pose distinguishes open hand, fist and fingertip pinch',()=>{
  assert.equal(pose(hand()).grip,false);assert.equal(pose(hand(.5,true)).grip,true);
  const p=hand();p[4]={...p[8]};assert.equal(pose(p).grip,true);
});
test('grab anywhere, slowly move a little left and release exactly one page',()=>{
  const g=new GrabGesture();grab(g,.8);
  assert.equal(g.update(hand(.72,true),2).page,0);
  const result=release(g,.70,3);assert.equal(result.page,1);
  assert.equal(g.update(hand(.8),3.4).page,0);
});
test('small right grab movement returns previous page',()=>{
  const g=new GrabGesture();grab(g,.2);assert.equal(release(g,.30,.5).page,-1);
});
test('grip requires an open hand first; a brief detection glitch is ignored',()=>{
  const g=new GrabGesture();assert.equal(g.update(hand(.5,true),0).grabbed,false);
  grab(g,.5,1);g.update(hand(.35,true),1.3);g.update(hand(.35),1.4);
  assert.equal(g.update(hand(.35,true),1.45).grabbed,true);
  assert.equal(release(g,.35,1.7).page,1);
});
test('lost hand cancels the grab without changing an artwork',()=>{
  const g=new GrabGesture();grab(g);g.update(hand(.2,true),.4);g.update(null,.5);
  const result=g.update(null,.9);assert.equal(result.page,0);assert.equal(result.cancel,true);
});
test('short movement springs back and does not advance',()=>{
  const g=new GrabGesture();grab(g);assert.equal(release(g,.48,.5).page,0);
});
test('sensitivity lets very small movements advance',()=>{
  const g=new GrabGesture({distance:.05});grab(g);assert.equal(release(g,.44,.5).page,1);
});
test('easy swipe works outside the center without a dwell',()=>{
  const g=new EasySwipe();g.update(hand(.85),0);
  assert.equal(g.update(hand(.75),.2).page,1);
  assert.equal(g.update(hand(.9),.4).page,0);
});
