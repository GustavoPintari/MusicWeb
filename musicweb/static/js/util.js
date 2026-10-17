// Small shared helpers and the page's shared state.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

const PLAY='<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE='<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
const $=s=>document.querySelector(s);

// shared state: the library, the player status and what is on screen
let lib=[],byId={},trackAlbum={},S={state:"stopped"},recvAt=0,openAlbum=null,openArtists=new Set();
let view="albums";try{view=localStorage.getItem("view")||"albums"}catch(e){}

const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt=s=>{s=Math.max(0,Math.floor(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=String(s%60).padStart(2,"0");return h?`${h}:${String(m).padStart(2,"0")}:${x}`:`${m}:${x}`};
const hue=s=>{let h=0;for(const c of s)h=(h*31+c.charCodeAt(0))%360;return h};
const cover=(a,cls="",eager=false)=>`<div class="cv ${cls}" style="--ph:hsl(${hue((a.name||"")+(a.artist||""))} 35% 28%)">${esc(((a.name||"").match(/[\p{L}\p{N}]/u)||["♪"])[0].toUpperCase())}<img loading="${eager?"eager":"lazy"}" src="/api/cover/${a.id}?v=${a.cv||0}" onload="this.classList.add('ok')" onerror="this.remove()" alt=""></div>`;

async function api(p,body,btn){
  btn?.classList.add("busy");navigator.vibrate?.(10);
  try{
    let r;
    try{r=await fetch("/api/"+p,{method:"POST",body:JSON.stringify(body||{})})}
    catch(e){$("#err").textContent=T("Sem conexão com o servidor");return}
    try{show(await r.json())}catch(e){console.error(e);$("#err").textContent=T("Erro na página: ")+e.message}
  }finally{btn?.classList.remove("busy")}
}

const LOSSLESS=new Set(["FLAC","ALAC","WAV"]);
function fmtBadge(f,q){if(!f)return"";return `<span class="fb${LOSSLESS.has(f)?" hq":""}">${esc(f)}${q?" "+esc(q):""}</span>`}
function albumFmt(a){
  const fs=[...new Set(a.tracks.map(t=>t.fmt).filter(Boolean))];
  if(fs.length!==1)return {f:fs.join(" · "),q:"",mixed:fs.length>1};
  const qs=[...new Set(a.tracks.map(t=>t.q).filter(Boolean))];
  return {f:fs[0],q:qs.length===1?qs[0]:"",mixed:false};
}

function toast(msg,ms=3500){const t=$("#toast");t.textContent=msg;t.classList.add("show");clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove("show"),ms)}
