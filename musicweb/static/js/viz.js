// Player bar visuals: the "aurora" behind the frosted glass (the colors of the album that is playing, breathing
// with the music) and the animated progress track (smooth fill, thumb, drag to seek, pulse on the beat).
// Plain script (no modules): the files share one global scope and load in order (see index.html).

const calm=matchMedia("(prefers-reduced-motion: reduce)");

// ---------- the music's energy (0..1): measured from this device's audio when the browser allows it,
// otherwise a simulated beat (Receiver output, Firefox/Safari, radios that don't send CORS headers).
// captureStream only copies the audio, so playback never depends on the analyser (Firefox's mozCaptureStream
// would mute the page, so it is not used).
const E={level:0,kick:0,avg:0};
let actx=null,an=null,anSrc=null,anTrack=null,anStream=null,fbin=null,silent=0;
function anHook(){
  if(!au.captureStream||!window.AudioContext)return;
  try{
    if(!actx){
      actx=new AudioContext();
      an=actx.createAnalyser();an.fftSize=512;an.smoothingTimeConstant=.6;fbin=new Uint8Array(an.frequencyBinCount);
      const mute=actx.createGain();mute.gain.value=0;an.connect(mute).connect(actx.destination);   // keeps the graph running, heard nowhere
      anStream=au.captureStream();
    }
    if(actx.state==="suspended")actx.resume();
    const tr=anStream.getAudioTracks()[0];   // a new track comes with each new source
    if(!tr||tr===anTrack)return;
    anSrc?.disconnect();anTrack=tr;silent=0;
    anSrc=actx.createMediaStreamSource(new MediaStream([tr]));anSrc.connect(an);
  }catch(e){an=null}
}
au.addEventListener("playing",anHook);

function measure(dt,playing){
  let lv=0,real=false;
  if(playing&&mode==="local"&&an&&anTrack){
    an.getByteFrequencyData(fbin);
    let b=0,m=0;for(let i=1;i<4;i++)b+=fbin[i];for(let i=4;i<48;i++)m+=fbin[i];
    lv=(b/3*.65+m/44*.35)/255;
    silent=lv<.01?silent+dt:0;               // a radio without CORS comes through as silence
    real=silent<1.5;
  }
  if(playing&&!real){                       // ~112 bpm, with a little variation so it doesn't feel mechanical
    const ph=performance.now()/1000*112/60;
    lv=.38+.15*Math.sin(ph*.21)+.3*Math.pow(Math.max(0,Math.cos(ph*Math.PI*2)),8)*(.75+.25*Math.sin(ph*1.7));
  }
  E.avg+=(lv-E.avg)*Math.min(1,dt*1.5);    // the beat is how far above its recent average the level jumps
  const k=playing&&!calm.matches?Math.min(1,Math.max(0,(lv-E.avg)*5)):0;
  E.kick+=(k-E.kick)*Math.min(1,dt*(k>E.kick?25:6));
  E.level+=(lv-E.level)*Math.min(1,dt*(lv>E.level?12:3));
}

// ---------- aurora
const AU={cols:null,next:undefined,vis:0,ph:0};
const lit=(c,l)=>c.replace(/[\d.]+%\)$/,l+"%)");
function vizTint(c){                        // c: albumTint() colors of the playing album, or null (radio, nothing)
  AU.next=c&&c.ac?[c.ac,lit(c.bg2,50),lit(c.bg3,50),lit(c.bg,46)]:null;
  if(!AU.cols)AU.cols=AU.next;              // nothing on screen yet: no need to fade out first
  vizWake();
}
const BLOBS=[[.9,1.3,0,1.15],[.6,1.7,2.1,.95],[.75,.9,4.2,1.05],[.5,1.1,1.3,.85]];   // speed x, speed y, offset, size
function aurora(dt,playing){
  const cv=$("#aura"),q=4,w=Math.ceil(cv.clientWidth/q),h=Math.ceil(cv.clientHeight/q);   // drawn small and scaled up: it's all blur anyway
  if(!w||!h)return false;
  if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h}
  const swap=AU.next!==undefined&&AU.next!==AU.cols;
  const goal=swap||!S.track||S.state==="stopped"?0:playing?1:.45;
  AU.vis+=(goal-AU.vis)*Math.min(1,dt*(swap?5:2.5));
  if(swap&&AU.vis<.03){AU.cols=AU.next;AU.next=undefined}
  if(!swap&&AU.next!==undefined)AU.next=undefined;
  if(!calm.matches)AU.ph+=dt*(playing?.3+E.level*.6:.06);
  const x=cv.getContext("2d");x.clearRect(0,0,w,h);
  if(AU.vis>.005){
    const cols=AU.cols||[getComputedStyle(cv).getPropertyValue("--ac").trim()||DEFAULT_AC,"hsl(200 70% 42%)","hsl(250 55% 48%)","hsl(180 55% 38%)"];
    const bh=$("#bar").offsetHeight/q,cy=h-bh*.55;
    x.globalCompositeOperation="lighter";
    BLOBS.forEach(([sx,sy,o,k],i)=>{
      const px=w*(.5+.42*Math.sin(AU.ph*sx+o)),py=cy+bh*.35*Math.sin(AU.ph*sy+o*1.7);
      const r=Math.max(bh*1.2,w*.22)*k*(.85+.35*E.level+.3*E.kick);
      const g=x.createRadialGradient(px,py,0,px,py,r);
      g.addColorStop(0,cols[i%cols.length]);g.addColorStop(1,"transparent");
      x.globalAlpha=AU.vis*Math.min(.75,.3+.3*E.level+.2*E.kick);
      x.fillStyle=g;x.fillRect(0,0,w,h);
    });
    x.globalAlpha=1;x.globalCompositeOperation="source-over";
  }
  return Math.abs(goal-AU.vis)>.005||swap;  // still fading
}

// ---------- progress track: drawn every frame; a jump (seek, next track) slides instead of snapping
let shown=0,progDrag=null;
function progress(dt){
  const [t,d]=curTime(),target=progDrag?progDrag.f:d&&S.track?t/d:0;
  const jump=Math.abs(target-shown)>.01&&!progDrag&&!calm.matches;
  shown=jump?shown+(target-shown)*Math.min(1,dt*12):target;
  const pc=(shown*100)+"%";
  $("#prog .fl").style.width=pc;$("#prog .th").style.left=pc;
  return jump;
}
const prog=$("#prog");
function progAt(e){const r=prog.getBoundingClientRect();return Math.min(1,Math.max(0,(e.clientX-r.left)/r.width))}
function progTip(f){const tp=prog.querySelector(".tip");tp.style.left=(f*100)+"%";tp.textContent=fmt(f*(S.dur||0))}
prog.addEventListener("pointerdown",e=>{
  if(!S.dur||!S.track||S.track.radio)return;
  prog.setPointerCapture(e.pointerId);progDrag={f:progAt(e)};
  prog.classList.add("drag","tipon");progTip(progDrag.f);$("#tc").textContent=fmt(progDrag.f*S.dur);vizWake();
});
prog.addEventListener("pointermove",e=>{
  const f=progAt(e);
  if(progDrag){progDrag.f=f;$("#tc").textContent=fmt(f*S.dur);vizWake()}
  if(S.dur&&S.track&&!S.track.radio&&(progDrag||e.pointerType==="mouse")){prog.classList.add("tipon");progTip(f)}
});
function progEnd(e,go){
  if(!progDrag)return;
  const f=progDrag.f;progDrag=null;prog.classList.remove("drag");
  if(e.pointerType!=="mouse")prog.classList.remove("tipon");
  if(go&&S.dur){shown=f;ctl.seek(f*S.dur)}
  tick();
}
prog.addEventListener("pointerup",e=>progEnd(e,true));
prog.addEventListener("pointercancel",e=>progEnd(e,false));
prog.addEventListener("pointerleave",()=>{if(!progDrag)prog.classList.remove("tipon")});

// ---------- one animation loop for both; it stops by itself when nothing moves (paused, faded out)
let vzRaf=0,vzLast=0;
function vizWake(){if(!vzRaf){vzLast=performance.now();vzRaf=requestAnimationFrame(vizFrame)}}
function vizFrame(now){
  const dt=Math.min(.1,(now-vzLast)/1000);vzLast=now;
  const playing=S.state==="playing";
  measure(dt,playing);
  $("#bar").style.setProperty("--kick",E.kick.toFixed(3));
  const moving=aurora(dt,playing)|progress(dt);
  vzRaf=playing||moving||progDrag||E.kick>.002?requestAnimationFrame(vizFrame):0;
  if(!vzRaf)$("#bar").style.setProperty("--kick","0");
}
