// Events and startup. Loaded last: everything above is defined by now.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// events
document.querySelector(".seg").onclick=e=>{const b=e.target.closest("button");if(!b)return;view=b.dataset.v;try{localStorage.setItem("view",view)}catch(e){};if(view==="plays")P.data=null;render()};
$("#q").oninput=render;
addEventListener("scroll",()=>document.body.classList.toggle("scrolled",scrollY>4),{passive:true});
$("#lib").onclick=e=>{
  if(e.target.closest("#rtb")){openSheet("@retro");return}
  const pd=e.target.closest(".per button");if(pd){P.days=+pd.dataset.days;try{localStorage.setItem("pdays",P.days)}catch(e){};P.data=null;renderPlays();return}
  const pa=e.target.closest(".pa");if(pa){view="artists";$("#q").value=pa.dataset.artist;try{localStorage.setItem("view",view)}catch(e){};render();return}
  const hr=e.target.closest(".hr");if(hr){playFromHistory(hr.dataset.h,hr);return}
  const al=e.target.closest(".al");if(al){openSheet(al.dataset.a);return}
  const ar=e.target.closest(".ar>button");if(ar){const box=ar.parentNode,n=box.dataset.ar;box.classList.toggle("open");box.classList.contains("open")?openArtists.add(n):openArtists.delete(n)}
};
function openSheet(id){
  const wasOpen=$("#sheet").classList.contains("open");
  openAlbum=id;editing=false;renderSheet();$("#sheet").scrollTop=0;$("#sheet").classList.remove("scrolled");$("#sheet").classList.add("open");
  if(!wasOpen)pushLayer("sheet");
  $("#lyb").classList.toggle("on",id==="@ly");$("#sheet").classList.toggle("lyr",id==="@ly");fitBar();
}
function closeSheet(){$("#sheet").classList.remove("open","lyr");openAlbum=null;editing=false;$("#lyb").classList.remove("on");setTint();fitBar()}
$("#back").onclick=()=>history.back();

// The album page (sheet) and the expanded player are layers in the browser history, so "back" (Android's button,
// the browser's) closes the top one. layers: what each history entry we pushed opened, oldest first.
const layers=[];let afterPop=null,popCount=0;
function pushLayer(l){layers.push(l);history.pushState({[l]:1},"")}
function closeLayers(n,then){                // goes back n entries, then runs "then"
  if(n<=0){then?.();return}
  afterPop=then;popCount=n;history.go(-n);
}
$("#sheet").addEventListener("scroll",e=>e.target.classList.toggle("scrolled",e.target.scrollTop>4),{passive:true});
window.onpopstate=()=>{
  const n=popCount||1;popCount=0;
  if(!layers.length){closeSheet();fullOff()}
  for(let i=0;i<n&&layers.length;i++)layers.pop()==="full"?fullOff():closeSheet();
  const f=afterPop;afterPop=null;f?.();
};
$("#sheetBody").onclick=e=>{
  const fv=e.target.closest("[data-fav]");if(fv){toggleFav(fv.dataset.fav,fv);return}
  const rr=e.target.closest(".rr");if(rr){playRadio(rr.dataset.r,rr);return}
  const tg=e.target.closest("[data-tag]");if(tg){R.tag=R.tag===tg.dataset.tag?"":tg.dataset.tag;
    document.querySelectorAll("[data-tag]").forEach(b=>b.classList.toggle("on",b.dataset.tag===R.tag));radioSearch();return}
  const hh=e.target.closest(".hr[data-h]");if(hh){playFromHistory(hh.dataset.h,hh);return}
  if(e.target.closest("#lyre")){e.preventDefault();const w=$("#lyfw");w.hidden=!w.hidden;if(!w.hidden)w.scrollIntoView({behavior:"smooth",block:"center"});return}
  const lp=e.target.closest(".ly p[data-i]");if(lp&&S.track?.id===LY.tid){ctl.seek(LY.lines[+lp.dataset.i].t);lyUserScroll=0;return}
  if(e.target.closest("#editAlbum")){editing=true;renderSheet();$("#sheet").scrollTop=0;return}
  if(e.target.closest("#e_cancel")){editing=false;renderSheet();return}
  if(e.target.closest("#e_find")){const cs=$("#cs");cs.classList.toggle("open");if(cs.classList.contains("open")&&!$("#csr").children.length)searchCovers();return}
  const cc=e.target.closest("#csr .c");if(cc){pickCover(cc);return}
  if(e.target.closest("#e_del")){$("#delbox").classList.add("open");$("#delbox").scrollIntoView({behavior:"smooth",block:"center"});return}
  if(e.target.closest("#e_delno")){$("#delbox").classList.remove("open");return}
  const dk=e.target.closest("#e_delok");if(dk){deleteAlbum(dk);return}
  const sv=e.target.closest("#e_save");if(sv){saveEdit(sv);return}
  if(editing)return;
  const b=e.target.closest("#playAll");if(b){ctl.playAlbum(openAlbum,b);return}
  const t=e.target.closest(".t");if(t){t.classList.add("busy");Promise.resolve(ctl.playTrack(t.dataset.t)).finally(()=>t.classList.remove("busy"))}
};
$("#sheetBody").onchange=e=>{
  if(e.target.id==="e_file"&&e.target.files[0])uploadCover(e.target.files[0]);
  if(e.target.id==="rdc")radioSearch();
  if(e.target.id==="rtsel"){RT.period=e.target.value;loadRetro()}
};
$("#sheetBody").onsubmit=e=>{
  if(e.target.id==="csf"){e.preventDefault();searchCovers()}
  if(e.target.id==="rdf"){e.preventDefault();radioSearch()}
  if(e.target.id==="lyf"){e.preventDefault();e.target.querySelector("button").classList.add("busy");
    fetchLyrics(LY.tid,$("#lya").value.trim(),$("#lyt").value.trim())}
};
// tap on the track: with a mouse and a wide window it opens the album page; elsewhere (phone, tablet) the
// expanded player; in the expanded player, the album page
$("#now").onclick=()=>{
  if(!S.track)return;
  const page=()=>{if(openAlbum!=="@ly"&&$("#sheet").classList.contains("open"))return;openSheet(byId[S.track.album]?S.track.album:"@radio")};
  if(isFull())leaveFull(page);else if(bigScreen.matches)page();else enterFull();
};
$("#rdb").onclick=()=>openSheet("@radio");
$("#lyb").onclick=()=>{navigator.vibrate?.(10);if(openAlbum==="@ly")history.back();else openSheet("@ly")};   // in the expanded player too
$("#pp").onclick=e=>ctl.toggle(e.currentTarget);
$("#nx").onclick=e=>ctl.next(e.currentTarget);
$("#pv").onclick=e=>ctl.prev(e.currentTarget);
$("#st").onclick=e=>ctl.stop(e.currentTarget);
$("#sh").onclick=e=>ctl.shuffle(e.currentTarget);
$("#rp").onclick=e=>ctl.repeat(e.currentTarget);

// expanded player: the bar takes the whole window, with the cover big and every control. On desktop (#fs button,
// F) the browser goes full screen too when it allows it; on a phone it opens with a tap on the track and closes
// with ⌄, a swipe down or "back". The lyrics (Letra) open beside the cover (below the title on a phone).
const bigScreen=matchMedia("(hover:hover) and (pointer:fine) and (min-width:820px)");
const FS_ON='<svg viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>';
const FS_OFF='<svg viewBox="0 0 24 24"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>';
const isFull=()=>document.body.classList.contains("full");
function fullView(on){
  document.body.classList.toggle("full",on);
  const b=$("#fs");b.innerHTML=on?FS_OFF:FS_ON;b.title=T(on?"Sair da tela cheia":"Tela cheia");b.classList.toggle("on",on);
  fitBar();vizWake();
  if(openAlbum==="@ly"&&LY.idx>=0)setTimeout(()=>document.querySelector(`.ly p[data-i="${LY.idx}"]`)?.scrollIntoView({block:"center"}),50);
}
function enterFull(){
  if(isFull()||!S.track&&!bigScreen.matches)return;
  navigator.vibrate?.(10);pushLayer("full");fullView(true);
  if(bigScreen.matches)document.documentElement.requestFullscreen?.().catch(()=>{});
}
function fullOff(){                         // called when its history entry is gone
  if(!isFull())return;
  fullView(false);
  if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
}
function leaveFull(then){                   // closes the expanded player and whatever was opened on top of it
  const i=layers.lastIndexOf("full");
  if(i<0){fullOff();then?.();return}
  closeLayers(layers.length-i,then);
}
$("#fs").onclick=()=>isFull()?leaveFull():enterFull();
$("#fdn").onclick=()=>leaveFull();
document.addEventListener("fullscreenchange",()=>{if(!document.fullscreenElement&&isFull())leaveFull()});   // Esc in browser full screen
let swipe=null;                             // phone: swipe down on the expanded player closes it
$("#bar").addEventListener("touchstart",e=>{swipe=isFull()&&!e.target.closest("#prog,#volpop,.ctl")?{y:e.touches[0].clientY,t:performance.now()}:null},{passive:true});
$("#bar").addEventListener("touchend",e=>{
  if(swipe&&e.changedTouches[0].clientY-swipe.y>90&&performance.now()-swipe.t<600)leaveFull();
  swipe=null;
},{passive:true});

// keyboard shortcuts (anywhere on the page, except while typing)
const KEYS=[["Espaço","tocar/pausar"],["← →","5 s"],["Shift+← →","faixa anterior/próxima"],["+ −","volume"],["M","mudo"],
  ["S","ordem aleatória"],["R","repetir"],["L","letra"],["V","visualizador"],["F","tela cheia"],["Esc","fechar"]];
addEventListener("keydown",e=>{
  if(e.ctrlKey||e.metaKey||e.altKey||e.target.closest?.("input,textarea,select,[contenteditable]"))return;
  const k=e.key.length===1?e.key.toLowerCase():e.key,full=isFull();
  const seekBy=d=>{const [t,dur]=curTime();if(S.track&&!S.track.radio&&dur)ctl.seek(Math.max(0,Math.min(dur-1,t+d)))};
  const act={
    " ":()=>ctl.toggle($("#pp")),k:()=>ctl.toggle($("#pp")),
    ArrowLeft:()=>e.shiftKey?ctl.prev($("#pv")):seekBy(-5),ArrowRight:()=>e.shiftKey?ctl.next($("#nx")):seekBy(5),
    "+":()=>ctl.volDelta(5),"=":()=>ctl.volDelta(5),"-":()=>ctl.volDelta(-5),
    ArrowUp:full&&(()=>ctl.volDelta(5)),ArrowDown:full&&(()=>ctl.volDelta(-5)),
    m:()=>{const on=(S.volume??100)>0;ctl.mute();toast(T(on?"Mudo":"Som ligado"),1200)},
    s:()=>ctl.shuffle($("#sh")),r:()=>ctl.repeat($("#rp")),l:()=>$("#lyb").click(),v:()=>$("#vzb").click(),
    f:bigScreen.matches&&(()=>$("#fs").click()),
    Escape:()=>{if(full)leaveFull();else if($("#sheet").classList.contains("open"))history.back()},
    "?":()=>toast(KEYS.map(([a,b])=>`${T(a)}: ${T(b)}`).join(" · "),9000),
  }[k];
  if(!act)return;
  e.preventDefault();act();
});
$("#rs").onclick=async e=>{const b=e.currentTarget;await api("rescan",null,b);b.classList.add("busy");await load();b.classList.remove("busy")};

let volDragging=false,volTimer=null;
// the volume row and the "⋯" row open below the controls, one at a time
function popRow(btn,row){
  navigator.vibrate?.(10);const open=!$(row).classList.contains("open");
  for(const [b,r] of [["#vol","#volpop"],["#more","#morepop"]]){
    const on=open&&r===row;$(r).classList.toggle("open",on);$(b).classList.toggle("on",on);$(b).setAttribute("aria-expanded",on);
  }
  fitBar();
}
$("#vol").onclick=()=>popRow("#vol","#volpop");
$("#more").onclick=()=>popRow("#more","#morepop");
$("#vr").oninput=e=>{volDragging=true;const v=+e.target.value;volSet(v);
  clearTimeout(volTimer);volTimer=setTimeout(()=>ctl.volume(v).finally(()=>volDragging=false),120)};
$("#vdn").onclick=e=>ctl.volDelta(-5,e.currentTarget);
$("#vup").onclick=e=>ctl.volDelta(5,e.currentTarget);

let libVer=null;
async function load(){
  const d=await (await fetch("/api/library")).json();libVer=d.lib;
  if(d.api!==2){$("#lib").innerHTML=`<p class="empty" style="color:var(--err)">${T("O server.py no celular está desatualizado.")}<br>${T("Copie a versão nova e reinicie o servidor.")}</p>`;return}
  lib=d.albums;byId={};trackById={};playerName=d.player||"Receiver";renderOut();
  historyOn=d.history!==false;playMin=d.play_min||30;
  lib.forEach(a=>{byId[a.id]=a;a.tracks.forEach(t=>trackById[t.id]={t,a})});
  Object.values(radioKnown).forEach(regRadio);
  loadRadios();render();if(openAlbum&&!editing)renderSheet();   // don't wipe a form being edited
}
async function poll(){
  try{
    const st=await (await fetch("/api/status",{headers:HDR})).json();
    if(mode==="local"){if(st.lib!=null&&libVer!=null&&st.lib!==libVer){libVer=st.lib;load()}return}
    show(st);
  }catch(e){}
}
renderOut();
load().then(()=>mode==="local"?show(localStatus()):poll());
setInterval(poll,2500);setInterval(tick,250);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)poll()});
