// YouTube videos and playlists.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- YouTube: each video becomes a single "track" in an "album" with the same id
let ytList=[];const ytKnown={};
function regYT(y){
  const t={id:y.id,title:y.title,artist:y.artist,dur:y.dur,fmt:y.fmt,q:y.q,n:0,disc:1};
  const a={id:y.id,name:y.title,full:y.title,artist:y.artist,year:"",cv:0,yt:true,tracks:[t]};
  trackById[y.id]={t,a};return a;
}
function regPL(pl){                         // playlist videos share one tracks list, so the queue is the whole playlist
  const ts=pl.entries.map((e,i)=>({id:e.id,title:e.title,artist:e.artist,dur:e.dur,fmt:e.fmt,q:e.q,n:i+1,disc:1}));
  pl.entries.forEach((e,i)=>trackById[e.id]={t:ts[i],a:{id:e.id,name:e.title,full:e.title,artist:e.artist,year:"",cv:0,yt:true,pl:pl.id,tracks:ts}});
  return ts.map(t=>t.id);
}
async function playPlaylist(pl,pos=0){
  if(!pl.entries){
    const r=await fetch("/api/yt_playlist?id="+encodeURIComponent(pl.id));
    if(!r.ok)throw new Error(T("Não consegui abrir essa playlist"));
    pl=await r.json();
  }
  const ids=regPL(pl);
  return ctl.playQueue(ids,pos,pl.id);
}
function renderYT(){
  if(!$("#ytsh"))$("#sheetBody").innerHTML=`<div id="ytsh"><h1>YouTube</h1>
    <p class="note">${T("Cole o link de um vídeo ou de uma playlist para tocar só o áudio.")}</p>
    <form id="ytf"><input id="ytu" type="url" inputmode="url" placeholder="https://youtu.be/…" autocomplete="off" enterkeyhint="go">
      <button class="big" id="ytgo">${PLAY} ${T("Tocar")}</button></form><div id="yterr"></div><div id="ytr"></div></div>`;
  $("#ytr").innerHTML=ytList.length?`<div class="disc">${T("Tocados recentemente")}</div>`+ytList.map(a=>{
    if(a.playlist)return `<div class="t" data-pl="${a.id}"><span class="n"></span>${cover({id:a.id,name:a.title,artist:a.artist},"yth")}<span class="ti">${esc(a.title)}<small>${T("Playlist · {n} vídeos",{n:a.count})}${a.artist?" · "+esc(a.artist):""}</small></span><button class="x" data-x="${a.id}" title="${T("Tirar do histórico")}">✕</button></div>`;
    const t=a.tracks[0];
    return `<div class="t" data-t="${t.id}"><span class="n"></span>${cover(a,"yth")}<span class="ti">${esc(t.title)}<small>${esc(t.artist)}</small></span><span class="d">${t.dur?fmt(t.dur):""}</span><button class="x" data-x="${t.id}" title="${T("Tirar do histórico")}">✕</button></div>`}).join(""):"";
  markPlaying();
}
async function addYT(url){                 // registers a video or a playlist (asks the server/yt-dlp)
  let r;try{r=await (await fetch("/api/yt",{method:"POST",body:JSON.stringify({url})})).json()}
  catch(e){throw new Error(T("Sem conexão com o servidor"))}
  if(!r.ok)throw new Error(r.error||T("Não consegui abrir esse vídeo"));
  if(r.playlist){
    const pl=r.playlist;regPL(pl);
    ytList=[{playlist:true,id:pl.id,title:pl.title,artist:pl.artist,count:pl.count},...ytList.filter(x=>x.id!==pl.id)];
    return r;
  }
  ytKnown[r.item.id]=r.item;const a=regYT(r.item);ytList=[a,...ytList.filter(x=>x.id!==a.id)];
  return r;
}
async function playYT(){
  const u=$("#ytu").value.trim(),b=$("#ytgo");if(!u)return;
  b.classList.add("busy");b.disabled=true;$("#yterr").textContent="";navigator.vibrate?.(10);
  try{
    const r=await addYT(u);
    $("#ytu").value="";renderYT();
    if(r.playlist)await playPlaylist(r.playlist,r.start);
    else await ctl.playTrack(r.item.id);
  }catch(e){$("#yterr").textContent=e.message}
  finally{b.classList.remove("busy");b.disabled=false}
}
async function removeYT(id){
  ytList=ytList.filter(a=>a.id!==id);renderYT();
  try{await fetch("/api/yt_remove",{method:"POST",body:JSON.stringify({id})})}catch(e){}
}
