import {FilesetResolver, HandLandmarker} from '@mediapipe/tasks-vision';
let detector;
self.onmessage = async ({data}) => {
  try {
    if(data.type==='init') {
      const files=await FilesetResolver.forVisionTasks('/vendor/wasm');
      detector=await HandLandmarker.createFromOptions(files,{
        baseOptions:{modelAssetPath:'/model.task',delegate:'CPU'},
        runningMode:'VIDEO',numHands:1,
        minHandDetectionConfidence:.4,minHandPresenceConfidence:.4,minTrackingConfidence:.4
      });
      self.postMessage({type:'ready'});
    } else if(data.type==='frame') {
      try {
        const result=detector.detectForVideo(data.bitmap,data.timestamp);
        self.postMessage({type:'result',landmarks:result.landmarks[0] || null,timestamp:data.timestamp});
      } finally {data.bitmap.close();}
    }
  } catch(error) {
    self.postMessage({type:'error',message:error.message || String(error)});
  }
};
