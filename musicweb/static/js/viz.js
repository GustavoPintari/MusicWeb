// Player bar visuals: the music visualizer (a band above the progress track: "needles" or "hills", in the colors
// of the album that is playing), the animated progress track (smooth fill, thumb, drag to seek, pulse on the
// beat) and the smooth volume slider.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

const calm=matchMedia("(prefers-reduced-motion: reduce)");

// ---------- the music's spectrum (N bands, 0..1, bass first): measured from this device's audio when the browser
// allows it, otherwise simulated (Receiver output, Firefox/Safari, radios that don't send CORS headers).
// captureStream only copies the audio, so playback never depends on the analyser (Firefox's mozCaptureStream
// would mute the page, so it is not used).
const N=64,spec=new Float32Array(N),E={level:0,kick:0,avg:0};
let actx=null,an=null,anSrc=null,anTrack=null,anStream=null,fbin=null,bandBin=null,silent=0;
function anHook(){
  if(!au.captureStream||!window.AudioContext)return;
  try{
    if(!actx){
      actx=new AudioContext();
      an=actx.createAnalyser();an.fftSize=2048;an.smoothingTimeConstant=.5;an.minDecibels=-85;an.maxDecibels=-20;
      fbin=new Uint8Array(an.frequencyBinCount);
      const hz=actx.sampleRate/an.fftSize;  // bands spaced like hearing does: 50 Hz .. 14 kHz, logarithmic
      bandBin=Array.from({length:N+1},(_,j)=>Math.max(1,Math.round(50*Math.pow(280,j/N)/hz)));
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

const goal=new Float32Array(N);
function measure(dt,playing){
  let real=false;
  if(playing&&mode==="local"&&an&&anTrack){
    an.getByteFrequencyData(fbin);
    let sum=0;
    for(let j=0;j<N;j++){
      let m=0;for(let b=bandBin[j];b<=Math.max(bandBin[j],bandBin[j+1]-1);b++)m=Math.max(m,fbin[b]);
      goal[j]=Math.min(1,Math.pow(m/255,1.4)*(.85+.5*j/N));sum+=m;   // highs are quieter: lift them a little
    }
    silent=sum<N?silent+dt:0;                // a radio without CORS comes through as silence
    real=silent<1.5;
  }
  if(playing&&!real){                       // ~112 bpm, with some movement across the bands
    const T=performance.now()/1000,beat=Math.pow(Math.max(0,Math.cos(T*Math.PI*2*112/60)),6);
    for(let j=0;j<N;j++){const f=j/N;
      goal[j]=Math.min(1,(1-f*.75)*.5*(.55+beat*.8)+.3*Math.abs(Math.sin(T*2.3+j*.55))*(1-f*.5)+.07*Math.random())}
  }
  if(!playing)goal.fill(0);
  const up=1-Math.exp(-dt*30),down=1-Math.exp(-dt*7);
  let lv=0;
  for(let j=0;j<N;j++){spec[j]+=(goal[j]-spec[j])*(goal[j]>spec[j]?up:down);if(j<6)lv+=spec[j]/6}
  E.avg+=(lv-E.avg)*Math.min(1,dt*1.5);    // the beat is how far above its recent average the bass jumps
  const k=playing&&!calm.matches?Math.min(1,Math.max(0,(lv-E.avg)*5)):0;
  E.kick+=(k-E.kick)*Math.min(1,dt*(k>E.kick?25:6));
  E.level=lv;
}

// ---------- visualizer: "needles" | "hills" | "off", remembered on this device; off by default for reduced motion
const VZ=["needles","hills","off"],VZNAME={needles:"Agulhas",hills:"Morros",off:"Desligado"};
let vzMode=calm.matches?"off":"needles";
try{const v=localStorage.getItem("viz");if(VZ.includes(v))vzMode=v}catch(e){}
let vzCols=null,vzGrad=null;
const lit=(c,l)=>c.replace(/[\d.]+%\)$/,l+"%)");
function vizTint(c){                        // c: albumTint() colors of the playing album, or null (radio, nothing)
  vzCols=c&&c.ac?[c.ac,lit(c.bg2,62),lit(c.bg3,62)]:null;vzGrad=null;vizWake();
}
function vizShow(){                         // the band takes room in the bar only while it has something to show
  const on=vzMode!=="off"&&!!S.track,bar=$("#bar");
  if(bar.classList.contains("vz")!==on){bar.classList.toggle("vz",on);fitBar()}
  const b=$("#vzb");b.classList.toggle("on",vzMode!=="off");b.querySelector("span").textContent=T("Visualizador")+": "+T(VZNAME[vzMode]);
}
$("#vzb").onclick=()=>{
  navigator.vibrate?.(10);
  vzMode=VZ[(VZ.indexOf(vzMode)+1)%VZ.length];try{localStorage.setItem("viz",vzMode)}catch(e){}
  toast(T("Visualizador")+": "+T(VZNAME[vzMode]),1500);vizShow();vizWake();
};
const amp=f=>{                              // bass in the middle, highs to the sides, tapering at the edges
  const i=Math.min(N-1.001,Math.abs(f-.5)*2*N*.85),a=Math.floor(i),u=i-a;
  return (spec[a]*(1-u)+spec[a+1]*u)*Math.pow(Math.sin(Math.PI*f),.6);
};
let vzStep=0;
function visualizer(now){
  if(!$("#bar").classList.contains("vz"))return;
  const cv=$("#vzc"),d=devicePixelRatio||1,w=cv.clientWidth,h=cv.clientHeight;
  if(!w)return;
  if(cv.width!==Math.round(w*d)||cv.height!==Math.round(h*d)){cv.width=Math.round(w*d);cv.height=Math.round(h*d);vzGrad=null}
  const x=cv.getContext("2d");x.setTransform(d,0,0,d,0,0);x.clearRect(0,0,w,h);
  if(!vzGrad){
    const cols=vzCols||[getComputedStyle(cv).getPropertyValue("--ac").trim()||DEFAULT_AC,"hsl(320 55% 55%)","hsl(260 55% 62%)"];
    vzGrad=x.createLinearGradient(0,0,w,0);cols.forEach((c,i)=>vzGrad.addColorStop(i/(cols.length-1),c));
  }
  x.strokeStyle=vzGrad;x.beginPath();
  if(vzMode==="needles"){                   // thin lines around the middle, each with its own jitter
    const c=h/2,step=Math.floor(now/80);x.lineWidth=1.5;
    for(let i=1;i<w;i+=4){
      const j=.45+.55*Math.abs(Math.sin(i*12.9898+step*.7)),a=amp(i/w)*h*.48*j+1;
      x.moveTo(i,c-a);x.lineTo(i,c+a*.8);
    }
  }else{                                    // nested lines forming hills on a base line
    const base=h-1.5;x.lineWidth=1;
    for(let k=1;k<=8;k++)for(let i=0;i<=w;i+=3){
      const f=i/w,y=base-amp(f)*h*.95*Math.pow(Math.abs(Math.sin(f*Math.PI*4+.3)),1.5)*k/8;
      i?x.lineTo(i,y):x.moveTo(i,y);
    }
  }
  x.stroke();
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

// ---------- volume slider: glides to a new value (+/− buttons, another device changing it) instead of jumping
let volShown=null,volGoal=0,volRaf=0;
function volPaint(){$("#vr").value=volShown;$("#vl").textContent=Math.round(volShown)+"%"}
function volSet(v){cancelAnimationFrame(volRaf);volRaf=0;volShown=volGoal=v;volPaint()}   // follows the finger: no glide
function volShow(v){
  if(volShown==null||calm.matches){volSet(v);return}
  volGoal=v;if(volRaf)return;
  let last=performance.now();
  const step=now=>{
    volShown+=(volGoal-volShown)*Math.min(1,(now-last)/1000*14);last=now;
    if(Math.abs(volGoal-volShown)<.3)volShown=volGoal;
    volPaint();volRaf=volShown!==volGoal?requestAnimationFrame(step):0;
  };
  volRaf=requestAnimationFrame(step);
}

// ---------- one animation loop; it stops by itself when nothing moves (paused and settled)
let vzRaf=0,vzLast=0;
function vizWake(){vizShow();if(!vzRaf){vzLast=performance.now();vzRaf=requestAnimationFrame(vizFrame)}}
function vizFrame(now){
  const dt=Math.min(.1,(now-vzLast)/1000);vzLast=now;
  const playing=S.state==="playing";
  measure(dt,playing);
  $("#bar").style.setProperty("--kick",E.kick.toFixed(3));
  visualizer(now);
  const moving=progress(dt)||E.kick>.002||spec.some(v=>v>.002);
  vzRaf=playing||moving||progDrag?requestAnimationFrame(vizFrame):0;
  if(!vzRaf)$("#bar").style.setProperty("--kick","0");
}
