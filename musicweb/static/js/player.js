// Player: status from the server, the player bar, and the two outputs (Receiver / this device).
// Plain script (no modules): the files share one global scope and load in order (see index.html).

function markPlaying(){
  document.querySelectorAll(".t").forEach(e=>{
    const on=S.track&&e.dataset.t===S.track.id;e.classList.toggle("on",on);
    const n=e.querySelector(".n"),t=byId[openAlbum]?.tracks.find(x=>x.id===e.dataset.t);
    n.innerHTML=on&&S.state!=="stopped"?`<span class="eq${S.state==="paused"?" paused":""}"><i></i><i></i><i></i></span>`:(t?.n||"");
  });
  document.querySelectorAll(".al").forEach(e=>e.classList.toggle("on",!!S.track&&e.dataset.a===S.track.album));
  document.querySelectorAll(".hr").forEach(e=>e.classList.toggle("on",!!S.track&&(e.dataset.h===S.track.id||"radio_"+e.dataset.r===S.track.id)));
}

function show(s){
  const prevId=S.track?.id,prevLive=S.track?.live;S=s;recvAt=performance.now();
  $("#pp").innerHTML=s.state==="playing"?PAUSE:PLAY;
  $("#bar").classList.toggle("playing",s.state==="playing");
  const busy=mode==="remote"&&s.owner&&!s.owner.you;      // another device is playing on the Receiver
  $("#bar").classList.toggle("locked",!!busy);
  const note=busy?"🔒 "+T("Em uso por {who}",{who:s.owner.name}):"";if($("#note").textContent!==note)$("#note").textContent=note;
  $("#sh").classList.toggle("on",!!s.shuffle);$("#sh").setAttribute("aria-pressed",!!s.shuffle);moreShow();
  repShow(s.repeat);
  if($("#err").textContent!==(s.error||"")){$("#err").textContent=s.error||"";fitBar()}
  if(s.track?.id!==prevId){
    const a=s.track&&(byId[s.track.album]||trackById[s.track.id]?.a);
    $("#now").innerHTML=s.track?`${cover(a||{id:s.track.album,name:s.track.album_name,artist:""},"",true)}<div class="tx"><b>${esc(s.track.title)}</b><small>${nowSub(s.track)}</small></div>`:`<div class="tx"><small>${T("Nada tocando")}</small></div>`;
    document.title=s.track?`${s.track.title} - MusicWeb`:"MusicWeb";
    setHomeTheme(s.track);
    $("#nowfmt").innerHTML=s.track?fmtBadge(s.track.fmt,s.track.q):"";
    if(mode==="local")mediaMeta();
    if(openAlbum==="@ly")renderLyrics();
    if(view==="plays"&&prevId){P.data=null;renderPlays()}
  }else if(s.track?.radio&&s.track.live!==prevLive){      // radio: the song on air changed
    const sm=$("#now .tx small");if(sm)sm.innerHTML=nowSub(s.track);
    if(openAlbum==="@ly")renderLyrics();
  }
  if(mode==="remote"&&s.lib!=null&&libVer!=null&&s.lib!==libVer){libVer=s.lib;load()}
  if(s.volume!=null&&!volDragging)volShow(s.volume);
  markPlaying();tick();
}

function nowSub(tr){
  if(tr.radio)return `<span class="live">${T("AO VIVO")}</span> ${esc(tr.live||trackById[tr.id]?.t.country||tr.album_name||"")}`;
  return `${esc(tr.artist||tr.album_artist)} — ${esc(tr.album_name)}`;
}

function curTime(){                       // [position, duration] in seconds, interpolated between status polls
  let t=S.time||0;if(S.state==="playing")t+=(performance.now()-recvAt)/1000;
  if(mode==="local")t=au.currentTime||0;
  const d=S.dur||0;return [d?Math.min(t,d):t,d];
}
function tick(){                            // the fill of the track is drawn every frame by viz.js
  const [t,d]=curTime();
  lyTick(t);
  if(!progDrag)$("#tc").textContent=S.track?fmt(t):"";
  $("#td").textContent=S.track?.radio?T("AO VIVO"):S.track&&d?fmt(d):"";
  vizWake();
}

// ---------- repeat: "off" → "all" (the queue starts over) → "one" (the same track again)
const REP=["off","all","one"],REPNAME={off:"Repetir desligado",all:"Repetir a fila",one:"Repetir a faixa"};
const REP_ICON='<svg viewBox="0 0 24 24"><path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z"/></svg>';
const REP1_ICON='<svg viewBox="0 0 24 24"><path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z"/></svg>';
function repShow(r){
  r=REP.includes(r)?r:"off";const b=$("#rp");if(b.dataset.r===r)return;
  b.dataset.r=r;b.querySelector("i").innerHTML=r==="one"?REP1_ICON:REP_ICON;b.querySelector("span").textContent=T(REPNAME[r]);
  b.classList.toggle("on",r!=="off");moreShow();
}
// "⋯" opens a row with shuffle, repeat and the visualizer; it gets a dot while shuffle or repeat is on
function moreShow(){$("#more").classList.toggle("dot",$("#sh").classList.contains("on")||$("#rp").classList.contains("on"))}
// queue index after the current track on this device (same rules as the server's next_pos)
function localNext(skip){
  if(L.repeat==="one"&&!skip)return L.pos;
  return L.pos+1>=L.queue.length&&L.repeat!=="off"?0:L.pos+1;
}

// ---------- audio output: "remote" = phone on the receiver, "local" = this device
let mode="remote",playerName="Receiver",trackById={};
try{mode=localStorage.getItem("out")==="local"?"local":"remote"}catch(e){}
const au=new Audio();au.preload="auto";
const L={queue:[],pos:-1,err:"",shuffle:false,order:null,repeat:"off"};   // order: the queue before shuffling
try{L.shuffle=localStorage.getItem("lshuf")==="1";const r=localStorage.getItem("lrep");if(REP.includes(r))L.repeat=r}catch(e){}
try{const v=localStorage.getItem("lvol");if(v!=null)au.volume=Math.min(1,Math.max(0,+v))}catch(e){}

function localStatus(){
  const ti=L.pos>=0&&trackById[L.queue[L.pos]];
  const st=!ti?"stopped":(!au.paused?"playing":(au.ended?"stopped":"paused"));
  return {state:st,time:au.currentTime||0,dur:isFinite(au.duration)&&au.duration?au.duration:(ti?ti.t.dur:0),
    volume:Math.round(au.volume*100),error:L.err,shuffle:L.shuffle,repeat:L.repeat,
    track:ti&&{id:ti.t.id,title:ti.t.title,artist:ti.t.artist,album:ti.a.id,album_name:ti.t.radio?ti.t.country:ti.a.name,album_artist:ti.a.artist,
      fmt:ti.t.fmt,q:ti.t.q,radio:!!ti.t.radio,live:""}};
}
const lshow=()=>{if(mode==="local")show(localStatus())};

// HLS streams (.m3u8, used by some radios): Safari and Android play them natively; other browsers use hls.js,
// loaded only the first time one is needed
let hlsLib=null,hlsPlayer=null;
const isHls=t=>t?.radio&&(t.hls||/\.m3u8(\?|$)/i.test(t.url||""));
function loadHls(){
  return hlsLib??=new Promise((ok,fail)=>{const sc=document.createElement("script");
    sc.src="https://cdn.jsdelivr.net/npm/hls.js@1.5.20/dist/hls.min.js";sc.onload=()=>ok(window.Hls);sc.onerror=()=>{hlsLib=null;fail(new Error("hls.js"))};
    document.head.append(sc)});
}
function hlsStop(){if(hlsPlayer){hlsPlayer.destroy();hlsPlayer=null}}

// shuffle (same as the server's): the chosen track first, then the others in random order
function shuffled(ids,pos){
  const r=ids.filter((_,i)=>i!==pos);
  for(let i=r.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[r[i],r[j]]=[r[j],r[i]]}
  return [ids[pos],...r];
}
function localStart(ids,pos,t=0,autoplay=true){   // a new queue on this device; pos null: from the start
  L.order=ids;
  if(pos==null)pos=L.shuffle?Math.floor(Math.random()*ids.length):0;
  if(L.shuffle&&pos>=0&&pos<ids.length){ids=shuffled(ids,pos);pos=0}
  localPlay(ids,pos,t,autoplay);
}
function localShuffle(on){                  // reorders the queue without touching the track that is playing
  L.shuffle=on;try{localStorage.setItem("lshuf",on?"1":"0")}catch(e){}
  const cur=L.queue[L.pos];
  if(L.pos>=0&&cur!=null){
    if(on){L.order=L.queue;L.queue=shuffled(L.queue,L.pos);L.pos=0}
    else if(L.order?.includes(cur)){L.queue=L.order;L.pos=L.order.indexOf(cur)}
  }
  lshow();
}

let LC={tid:null};                          // listening counter for the current local track
function localPlay(queue,pos,t=0,autoplay=true){
  if(pos<0||pos>=queue.length){localStop();return}
  if(L.queue!==queue)L.fails=0;
  L.queue=queue;L.pos=pos;L.err="";LC={tid:queue[pos],heard:0,last:null,counted:false};
  hlsStop();
  const tr=trackById[queue[pos]]?.t,url=tr?.url||"/api/stream/"+queue[pos];       // radio: the stream itself
  const fail=e=>{
    if(e.name==="AbortError")return;         // another track was loaded meanwhile: not an error
    if(e.name!=="NotAllowedError"&&au.error)return;   // load failed: the "error" handler explains it
    L.err=e.name==="NotAllowedError"?T("Toque em ▶ para começar a tocar aqui"):T("Não consegui tocar: ")+e.message;lshow()};
  if(isHls(tr)&&!au.canPlayType("application/vnd.apple.mpegurl")){
    au.removeAttribute("src");
    loadHls().then(Hls=>{
      if(L.queue!==queue||L.pos!==pos)return;
      if(!Hls.isSupported())throw new Error(T("Este navegador não conseguiu tocar {what}",{what:"HLS"}));
      hlsPlayer=new Hls();hlsPlayer.loadSource(url);hlsPlayer.attachMedia(au);
      hlsPlayer.on(Hls.Events.ERROR,(ev,d)=>{if(d.fatal){L.err=T("Não consegui tocar: ")+(d.details||d.type);hlsStop();lshow()}});
      if(autoplay)au.play().catch(fail);
    }).catch(fail);
    lshow();return;
  }
  au.src=url;
  if(t>1)au.addEventListener("loadedmetadata",()=>{au.currentTime=t},{once:true});
  if(autoplay)au.play().catch(fail);
  lshow();
}
function localStop(){hlsStop();au.pause();au.removeAttribute("src");au.load();L.pos=-1;lshow()}
au.addEventListener("ended",()=>{
  if(L.repeat==="one"&&L.queue[L.pos]){au.currentTime=0;LC={tid:L.queue[L.pos],heard:0,last:null,counted:false};au.play().catch(()=>{});return}
  localPlay(L.queue,localNext())});
au.addEventListener("error",()=>{
  if(!au.getAttribute("src")||hlsPlayer)return;
  const q=L.queue,p=L.pos,tid=q[p],ti=trackById[tid];
  L.err=T("Este navegador não conseguiu tocar {what}",{what:(ti?.t.fmt||T("o arquivo"))+(ti?` (${ti.t.title})`:"")});
  lshow();
  L.fails=(L.fails||0)+1;
  if(L.fails>=3)return;                      // don't run through a whole album when every track fails
  setTimeout(()=>{if(L.err&&L.queue===q&&L.pos===p)localPlay(q,localNext(true))},2500);
});
au.addEventListener("playing",()=>{L.fails=0});
["play","pause","loadedmetadata"].forEach(ev=>au.addEventListener(ev,lshow));
au.addEventListener("timeupdate",()=>{
  if(mode!=="local"||!historyOn||!LC.tid||LC.counted||trackById[LC.tid]?.t.radio)return;   // radio is not counted
  const t=au.currentTime;
  if(LC.last!=null){const dt=t-LC.last;if(dt>0&&dt<2)LC.heard+=dt}   // jumps (seeking) don't count
  LC.last=t;
  const dur=trackById[LC.tid]?.t.dur||(isFinite(au.duration)?au.duration:0),need=dur&&dur<2*playMin?Math.max(1,dur/2):playMin;
  if(LC.heard>=need){
    LC.counted=true;
    fetch("/api/played",{method:"POST",body:JSON.stringify({id:LC.tid})}).then(()=>{if(view==="plays"){P.data=null;renderPlays()}}).catch(()=>{});
  }
});

function mediaMeta(){
  if(!("mediaSession" in navigator))return;
  const ti=trackById[L.queue[L.pos]];if(!ti)return;
  try{navigator.mediaSession.metadata=new MediaMetadata({title:ti.t.title,artist:ti.t.radio?T("Rádio ao vivo"):ti.t.artist||ti.a.artist,album:ti.t.radio?ti.t.country:ti.a.name,
    artwork:[{src:`/api/cover/${ti.a.id}?v=${ti.a.cv||0}`,sizes:"512x512"}]})}catch(e){}
}
if("mediaSession" in navigator){
  const ms=navigator.mediaSession,h=(a,f)=>{try{ms.setActionHandler(a,f)}catch(e){}};
  h("play",()=>au.play());h("pause",()=>au.pause());
  h("nexttrack",()=>ctl.next());h("previoustrack",()=>ctl.prev());
  h("seekto",d=>{au.currentTime=d.seekTime;lshow()});
}

// every control works in both modes
const ctl={
  playAlbum(aid,btn){const a=byId[aid];if(mode==="local")localStart(a.tracks.map(t=>t.id),null);else return api("play",{album:aid},btn)},
  playQueue(ids,pos=0,plid){if(mode==="local"){localStart(ids,pos);return Promise.resolve()}
    return plid?api("play",{playlist:plid,pos}):api("play",{queue:ids,pos})},
  playTrack(tid){const ti=trackById[tid];if(mode==="local"){const q=ti.a.tracks.map(t=>t.id);localStart(q,q.indexOf(tid));return Promise.resolve()}
    return api("play",{id:tid})},
  toggle(btn){
    if(!S.track)return;
    if(mode==="local"){navigator.vibrate?.(10);au.paused?au.play().catch(()=>{}):au.pause();return}
    const p=S.state==="playing";S.state=p?"paused":"playing";S.time=(S.time||0)+(p?(performance.now()-recvAt)/1000:0);recvAt=performance.now();
    btn.innerHTML=p?PLAY:PAUSE;api(p?"pause":"resume",null,btn)},
  next(btn){if(mode==="local"){navigator.vibrate?.(10);localPlay(L.queue,localNext(true))}else api("next",null,btn)},
  prev(btn){if(mode==="local"){navigator.vibrate?.(10);if(au.currentTime>5){au.currentTime=0;lshow()}else localPlay(L.queue,Math.max(0,L.pos-1))}
    else api("prev",null,btn)},
  shuffle(btn){const on=!S.shuffle;toast(on?T("Ordem aleatória ligada"):T("Ordem aleatória desligada"),1500);
    if(mode==="local"){navigator.vibrate?.(10);localShuffle(on);return Promise.resolve()}
    S.shuffle=on;$("#sh").classList.toggle("on",on);moreShow();return api("shuffle",{on},btn)},
  repeat(btn){const r=REP[(REP.indexOf(S.repeat||"off")+1)%REP.length];toast(T(REPNAME[r]),1500);repShow(r);S.repeat=r;
    if(mode==="local"){navigator.vibrate?.(10);L.repeat=r;try{localStorage.setItem("lrep",r)}catch(e){};lshow();return Promise.resolve()}
    return api("repeat",{mode:r},btn)},
  mute(){if((S.volume??100)>0){ctl.muted=S.volume;return ctl.volume(0)}return ctl.volume(ctl.muted||50)},
  stop(btn){if(mode==="local"){navigator.vibrate?.(10);localStop()}else api("stop",null,btn)},
  seek(t){if(mode==="local"){au.currentTime=t;lshow()}else{S.time=t;recvAt=performance.now();tick();api("seek",{t})}},
  volume(v){v=Math.max(0,Math.min(100,v));
    if(mode==="local"){au.volume=v/100;try{localStorage.setItem("lvol",au.volume)}catch(e){};lshow();return Promise.resolve()}
    return api("volume",{v})},
  volDelta(d,btn){if(mode==="local"){navigator.vibrate?.(10);return ctl.volume(Math.round(au.volume*100)+d)}return api("volume",{delta:d},btn)},
};

function renderOut(){
  const o=$("#out");o.classList.toggle("local",mode==="local");
  o.innerHTML=mode==="local"?T("Este dispositivo"):esc(playerName);
  o.title=T("Trocar onde a música toca");
}

// switch output, carrying over the track and position
async function switchOutput(){
  navigator.vibrate?.(10);$("#out").classList.add("busy");
  try{
    if(mode==="remote"){
      let st=null;try{st=await (await fetch("/api/status",{headers:HDR})).json()}catch(e){}
      mode="local";try{localStorage.setItem("out",mode)}catch(e){}
      const mine=!st?.owner||st.owner.you;   // another device's music stays on the Receiver; this one starts empty
      const ti=mine&&st?.track&&st.state!=="stopped"&&trackById[st.track.id];
      if(ti){
        const q=ti.a.tracks.map(t=>t.id),playing=st.state==="playing";
        fetch("/api/pause",{method:"POST",headers:HDR,body:'{"release":true}'});   // and frees the Receiver
        localStart(q,q.indexOf(ti.t.id),st.time||0,playing);
      }else show(localStatus());
      toast(T("Tocando neste dispositivo"));
    }else{
      let st=null;try{st=await (await fetch("/api/status",{headers:HDR})).json()}catch(e){}
      if(st?.owner&&!st.owner.you){toast(T("{name} está tocando para {who}. Continue ouvindo neste dispositivo.",{name:playerName,who:st.owner.name}),6000);return}
      const ti=L.pos>=0&&trackById[L.queue[L.pos]],playing=!au.paused,t=au.currentTime||0;
      au.pause();mode="remote";try{localStorage.setItem("out",mode)}catch(e){}
      S={state:"stopped"};
      if(ti&&(playing||t>0)){await api("play",{id:ti.t.id,t});if(!playing)await api("pause")}
      else await poll();
      toast(T("Tocando no {name}",{name:playerName}));
    }
  }finally{$("#out").classList.remove("busy");renderOut()}
}
$("#out").onclick=switchOutput;

// the player bar changes height (volume slider, error line, screen width): keep the page's
// bottom padding equal to it, so the last tracks can always be scrolled out from under it
// In the expanded player, --lyb is the room the title and controls take at the bottom: on a narrow screen the
// lyrics fill the space above them.
function fitBar(){
  const st=document.documentElement.style;st.setProperty("--barh",$("#bar").offsetHeight+"px");
  if(document.body.classList.contains("full"))st.setProperty("--lyb",(innerHeight-$("#now").getBoundingClientRect().top+8)+"px");
}
if("ResizeObserver" in window)new ResizeObserver(fitBar).observe($("#bar"));
fitBar();addEventListener("resize",fitBar);
