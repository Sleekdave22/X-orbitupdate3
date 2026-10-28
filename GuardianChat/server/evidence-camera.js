'use strict';
window.OrbitEvidenceCamera={mount({container,videoRequired=false,onCapture,onActive,purpose='evidence',maxSeconds=60,includeAudio=false}){
 const el=(tag,text='')=>{const x=document.createElement(tag);x.textContent=text;return x};
 const root=el('section'),preview=el('video'),photoPreview=el('img'),notice=el('p','Keep the PC/TV result screen open. Both gaming IDs, match details and final scores must be visible.');
 const vibe=purpose==='vibe';if(vibe)notice.textContent='Capture a Vibe. Videos can be up to '+maxSeconds+' seconds. Review it before publishing to your selected audience.';root.className='evidence-camera';preview.hidden=true;preview.autoplay=true;preview.muted=true;preview.playsInline=true;preview.setAttribute('aria-label','Your private camera preview');preview.style.cssText='width:100%;max-height:38vh;object-fit:contain;border-radius:14px;background:#080b18';
 photoPreview.hidden=true;photoPreview.alt='Your unsent camera photo';photoPreview.style.cssText=preview.style.cssText;
 const modes=el('div'),panel=el('section'),back=el('button',vibe?'‹ Back':'‹ Back to conversation'),open=el('button'),flip=el('button','↻'),shutter=el('button','●'),stop=el('button','Stop recording'),hint=el('p',videoRequired?'Video proof needed: tap to start, or hold and swipe up to lock.':'Tap the shutter for a photo. Hold for video; swipe up to lock.'),feedback=el('p');
 for(const b of [back,open,flip,shutter,stop])b.type='button';panel.hidden=true;
 if(vibe){hint.textContent=videoRequired?'Tap to start video, or hold and swipe up to lock.':'Tap for a photo. Hold for video; swipe up to lock.';preview.setAttribute('aria-label','Your unsent Vibe camera preview')}
 open.setAttribute('aria-label',vibe?'Open Vibe camera':'Capture result evidence with camera');open.title=vibe?'Capture a Vibe':'Capture photo or video evidence';open.className='evidence-camera-launcher';open.innerHTML='<svg viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 7h4l2-3h6l2 3h4v13H3Z"/><circle cx="12" cy="13" r="4"/></svg>';
 flip.setAttribute('aria-label','Switch camera');stop.hidden=true;shutter.disabled=true;
 shutter.setAttribute('aria-label','Camera shutter: tap photo, hold video, swipe up to lock');shutter.style.cssText='width:64px;height:64px;min-width:64px;border-radius:50%;font-size:30px;touch-action:none;user-select:none';
 modes.className='actions';modes.append(back,flip);panel.className='evidence-camera-panel';panel.append(modes,notice,preview,photoPreview,shutter,stop,hint,feedback);root.append(open,panel);container.append(root);
 let stream=null,recorder=null,parts=[],mode=videoRequired?'video':'photo',recording=false,finalizing=false,locked=false,destroyed=false,pressTimer=null,limitTimer=null,startY=0,url='',held=false,bytes=0,suppressClick=false,facing='environment',started=0,cameraGeneration=0;
 const active=()=>Boolean(stream||recording||finalizing);
 const announce=()=>onActive?.(active());
 function revoke(){if(url)URL.revokeObjectURL(url);url=''}
 function tracks(){stream?.getTracks().forEach(t=>t.stop());stream=null;preview.srcObject=null;announce()}
 function captured(blob){if(destroyed||panel.hidden)return;if(blob.size>20*1024*1024){feedback.textContent='Recording exceeded 20 MB. Make a shorter recording.';tracks();return}revoke();url=URL.createObjectURL(blob);preview.srcObject=null;const motion=blob.type.startsWith('video/');preview.hidden=!motion;photoPreview.hidden=motion;if(motion)preview.src=url;else photoPreview.src=url;preview.controls=motion;preview.loop=false;onCapture(blob);feedback.textContent=vibe?'Captured. Review before publishing your Vibe.':'Captured privately. Check it, then submit for review. Use the camera icon to retake.';shutter.disabled=true;tracks()}
 async function startCamera(){
  if(recording||finalizing||destroyed)return;panel.hidden=false;onCapture(null);const generation=++cameraGeneration;tracks();revoke();preview.removeAttribute('src');photoPreview.removeAttribute('src');photoPreview.hidden=true;preview.hidden=false;preview.controls=false;
  try{if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera capture is unavailable in this browser');
   const media=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:facing},width:{ideal:1280,max:1920},height:{ideal:720,max:1080}},audio:includeAudio});
   if(destroyed||generation!==cameraGeneration){media.getTracks().forEach(t=>t.stop());return}stream=media;preview.srcObject=stream;await preview.play();shutter.disabled=false;feedback.textContent=vibe?'Camera ready. Tap for a photo, or hold to record.':'Camera ready. Frame both gaming IDs and the final score.';announce();
  }catch(e){if(!destroyed&&generation===cameraGeneration){feedback.textContent='Camera unavailable: '+e.message;shutter.disabled=true}}
 }
 function stopRecording(){if(!recording)return;recording=false;finalizing=true;locked=false;clearTimeout(limitTimer);stop.hidden=true;shutter.textContent='●';if(recorder?.state!=='inactive')recorder.stop();announce()}
 function startRecording(){
  if(recording||finalizing||!stream||destroyed)return;
  try{
   if(typeof MediaRecorder==='undefined')throw Error('Video recording is unavailable');
   const mime=['video/webm;codecs=vp8','video/webm','video/mp4'].find(x=>MediaRecorder.isTypeSupported(x));
   if(!mime)throw Error('No supported video format');
   recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:1500000});parts=[];bytes=0;started=Date.now();
   recorder.ondataavailable=e=>{if(e.data.size){parts.push(e.data);bytes+=e.data.size;if(bytes>20*1024*1024)stopRecording()}};
   recorder.onerror=()=>{feedback.textContent='Recording interrupted. Please capture again.';recording=false;tracks()};
   const current=recorder;recorder.onstop=()=>{const ready=new Blob(parts,{type:current.mimeType});parts=[];finalizing=false;if(destroyed)return;if(Date.now()-started<3000){feedback.textContent=vibe?'Record at least 3 seconds.':'Record at least 3 seconds; 12–60 seconds is best for showing navigation.';tracks();return}captured(ready)};
   recorder.start(500);recording=true;stop.hidden=false;shutter.textContent='■';feedback.textContent=vibe?'Recording Vibe · slide up to lock. Maximum '+maxSeconds+' seconds.':'Recording · show navigation, match details, scores and both gaming IDs. Slide up to lock.';
   limitTimer=setTimeout(stopRecording,maxSeconds*1000);announce();
  }catch(e){feedback.textContent=e.message}
 }
 async function takePhoto(){
  if(!stream||finalizing||destroyed)return;
  const canvas=el('canvas');canvas.width=preview.videoWidth;canvas.height=preview.videoHeight;
  if(!canvas.width||!canvas.height){feedback.textContent='Wait for the camera preview';return}
  canvas.getContext('2d').drawImage(preview,0,0);canvas.toBlob(blob=>{canvas.width=canvas.height=1;if(blob)captured(blob);else feedback.textContent='Could not capture this photo'},'image/jpeg',.9);
 }
 back.onclick=()=>{panel.hidden=true;cameraGeneration++;clearTimeout(pressTimer);clearTimeout(limitTimer);if(recording)stopRecording();tracks();revoke();preview.hidden=photoPreview.hidden=true;shutter.disabled=true;onCapture(null);feedback.textContent=''};
 open.onclick=startCamera;flip.onclick=async()=>{if(recording)return;facing=facing==='environment'?'user':'environment';await startCamera()};stop.onclick=stopRecording;
 shutter.onpointerdown=e=>{if(!stream||destroyed)return;e.preventDefault();startY=e.clientY;held=false;suppressClick=true;shutter.setPointerCapture?.(e.pointerId);
  if(recording&&locked){stopRecording();return}
  if(mode==='video'){held=true;startRecording();locked=true}else pressTimer=setTimeout(()=>{held=true;startRecording()},350);
 };
 shutter.onpointermove=e=>{if(recording&&held&&startY-e.clientY>60){locked=true;feedback.textContent='Recording locked. Tap ■ or Stop recording when finished.'}};
 shutter.onpointerup=e=>{e.preventDefault();clearTimeout(pressTimer);if(recording){if(!locked)stopRecording()}else if(!held&&mode==='photo')takePhoto();held=false};
 shutter.onpointercancel=()=>{clearTimeout(pressTimer);if(recording&&!locked)stopRecording()};
 shutter.onclick=()=>{if(suppressClick){suppressClick=false;return}if(recording)stopRecording();else if(mode==='video')startRecording();else takePhoto()};
 return {root,active,destroy(){destroyed=true;cameraGeneration++;clearTimeout(pressTimer);clearTimeout(limitTimer);if(recorder?.state==='recording')recorder.stop();parts=[];tracks();revoke();root.remove()}};
}};
