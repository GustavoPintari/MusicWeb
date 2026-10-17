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
  if(!wasOpen)history.pushState({sheet:1},"");
  $("#lyb").classList.toggle("on",id==="@ly");
}
function closeSheet(){$("#sheet").classList.remove("open");openAlbum=null;editing=false;$("#lyb").classList.remove("on");setTint()}
$("#back").onclick=()=>history.back();
$("#sheet").addEventListener("scroll",e=>e.target.classList.toggle("scrolled",e.target.scrollTop>4),{passive:true});
window.onpopstate=closeSheet;
$("#sheetBody").onclick=e=>{
  const x=e.target.closest("[data-x]");if(x){removeYT(x.dataset.x);return}
  const fv=e.target.closest("[data-fav]");if(fv){toggleFav(fv.dataset.fav,fv);return}
  const rr=e.target.closest(".rr");if(rr){playRadio(rr.dataset.r,rr);return}
  const tg=e.target.closest("[data-tag]");if(tg){R.tag=R.tag===tg.dataset.tag?"":tg.dataset.tag;
    document.querySelectorAll("[data-tag]").forEach(b=>b.classList.toggle("on",b.dataset.tag===R.tag));radioSearch();return}
  const pl=e.target.closest("[data-pl]");if(pl){pl.classList.add("busy");playPlaylist({id:pl.dataset.pl}).catch(err=>toast(err.message,6000)).finally(()=>pl.classList.remove("busy"));return}
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
  if(e.target.id==="ytf"){e.preventDefault();playYT()}
  if(e.target.id==="rdf"){e.preventDefault();radioSearch()}
  if(e.target.id==="lyf"){e.preventDefault();e.target.querySelector("button").classList.add("busy");
    fetchLyrics(LY.tid,$("#lya").value.trim(),$("#lyt").value.trim())}
};
$("#now").onclick=()=>{if(S.track&&!$("#sheet").classList.contains("open"))openSheet(byId[S.track.album]?S.track.album:S.track.radio?"@radio":"@yt")};
$("#ytb").onclick=()=>{openSheet("@yt");$("#ytu").focus()};
$("#rdb").onclick=()=>openSheet("@radio");
$("#lyb").onclick=()=>{navigator.vibrate?.(10);if(openAlbum==="@ly")history.back();else openSheet("@ly")};
$("#pp").onclick=e=>ctl.toggle(e.currentTarget);
$("#nx").onclick=e=>ctl.next(e.currentTarget);
$("#pv").onclick=e=>ctl.prev(e.currentTarget);
$("#st").onclick=e=>ctl.stop(e.currentTarget);
$("#rs").onclick=async e=>{const b=e.currentTarget;await api("rescan",null,b);b.classList.add("busy");await load();b.classList.remove("busy")};
$("#prog").onclick=e=>{if(!S.dur||!S.track)return;const r=e.currentTarget.getBoundingClientRect(),t=(e.clientX-r.left)/r.width*S.dur;
  ctl.seek(t)};

let volDragging=false,volTimer=null;
$("#vol").onclick=e=>{navigator.vibrate?.(10);$("#volpop").classList.toggle("open");e.currentTarget.classList.toggle("on");fitBar()};
$("#vr").oninput=e=>{volDragging=true;const v=+e.target.value;$("#vl").textContent=v+"%";
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
  const vids=(d.yt||[]).filter(y=>!y.playlist);
  vids.forEach(y=>ytKnown[y.id]=y);Object.values(ytKnown).forEach(regYT);   // keep what is playing even if it left the history
  ytList=(d.yt||[]).map(y=>y.playlist?y:trackById[y.id].a);
  Object.values(radioKnown).forEach(regRadio);
  loadRadios();render();if(openAlbum&&!editing)renderSheet();   // don't wipe a form being edited
}
async function poll(){
  try{
    const st=await (await fetch("/api/status")).json();
    if(mode==="local"){if(st.lib!=null&&libVer!=null&&st.lib!==libVer){libVer=st.lib;load()}return}
    show(st);
  }catch(e){}
}
renderOut();
load().then(()=>mode==="local"?show(localStatus()):poll());
setInterval(poll,2500);setInterval(tick,250);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)poll()});
