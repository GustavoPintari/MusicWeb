// Lyrics of the track being played (synced or plain).
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- lyrics of the track being played
let LY={tid:null},lyUserScroll=0,lySeq=0;
function parseLRC(s){
  const out=[];
  for(const line of s.split(/\r?\n/)){
    const tags=[...line.matchAll(/\[(\d+):(\d+(?:[.:]\d+)?)\]/g)];if(!tags.length)continue;
    const text=line.replace(/\[[^\]]*\]/g,"").trim();
    for(const m of tags)out.push({t:+m[1]*60+parseFloat(m[2].replace(":",".")),text});
  }
  return out.sort((a,b)=>a.t-b.t);
}
const lyForm=(ar,ti)=>`<form id="lyf" class="ed"><label>${T("Artista")}</label><input id="lya" value="${esc(ar)}">
  <label>${T("Nome da música")}</label><input id="lyt" value="${esc(ti)}"><div class="acts" style="margin-top:12px"><button class="big">${T("Buscar letra")}</button></div></form>`;
function renderLyrics(force){
  const tr=S.track;
  if(!tr){LY={tid:null};$("#sheetBody").innerHTML=`<p class="empty">${T("Nada tocando.")}</p>`;return}
  const key=tr.radio?tr.id+"|"+(tr.live||""):tr.id;          // radio: new lyrics when the song on air changes
  if(!force&&LY.key===key&&$("#lyv"))return;
  LY={tid:tr.id,key,lines:null,idx:-1};
  const a=byId[tr.album]||trackById[tr.id]?.a||{id:tr.album,name:tr.album_name,artist:""};
  $("#sheetBody").innerHTML=`<div id="lyv"><div class="lyh">${cover(a,"",true)}<div><b>${esc(tr.title)}</b><small>${esc(tr.artist||tr.album_artist)}</small></div></div>
    <div id="lyc"><p class="empty">${T("Buscando letra…")}</p></div></div>`;
  if(tr.radio){                              // stations send "Artist - Song" (ICY metadata), when they send anything
    const m=(tr.live||"").split(/\s+-\s+/);
    if(m.length<2){$("#lyc").innerHTML=`<p class="empty">${T("Esta rádio não informa a música que está tocando.")}</p>`;return}
    return fetchLyrics(tr.id,m[0].trim(),m.slice(1).join(" - ").trim());
  }
  fetchLyrics(tr.id);
}
async function fetchLyrics(tid,artist,title,retry=1){
  const p=new URLSearchParams({id:tid});if(artist!=null){p.set("artist",artist);p.set("title",title)}
  const seq=++lySeq;
  let r;try{r=await (await fetch("/api/lyrics?"+p)).json()}catch(e){r={ok:false,error:T("Sem conexão com o servidor")}}
  if(seq!==lySeq||LY.tid!==tid||openAlbum!=="@ly")return;
  if(!r.ok&&r.error&&retry){                 // LRCLIB slow or busy: try again by itself before showing the error
    await new Promise(ok=>setTimeout(ok,1500));
    if(seq===lySeq&&LY.tid===tid&&openAlbum==="@ly")fetchLyrics(tid,artist,title,retry-1);
    return;
  }
  LY.lines=null;LY.idx=-1;
  const form=lyForm(r.artist??S.track?.artist??"",r.title??S.track?.title??"");
  let h;
  if(r.ok&&r.synced){LY.lines=parseLRC(r.synced);h=`<div class="ly">${LY.lines.map((l,i)=>`<p data-i="${i}">${esc(l.text)||"♪"}</p>`).join("")}</div>`}
  else if(r.ok&&r.plain)h=`<div class="ly plain">${esc(r.plain)}</div>`;
  else if(r.ok&&r.instrumental)h=`<p class="empty">♪ Instrumental</p>`;
  else h=`<p class="empty">${esc(r.error||T("Não encontrei a letra desta música."))}</p><p class="empty" style="margin-top:6px">${T("Confira o nome e tente de novo:")}</p>`;
  h+=r.ok?`<p class="lysrc">${T("Letra")}: ${esc(r.src)}${r.synced?" · "+T("sincronizada (toque numa linha para pular até ela)"):""} · <a href="#" id="lyre">${T("Letra errada? Buscar outra")}</a></p><div id="lyfw" hidden>${form}</div>`:form;
  $("#lyc").innerHTML=h;tick();
}
function lyTick(t){
  if(openAlbum!=="@ly"||!LY.lines||S.track?.id!==LY.tid)return;
  let i=-1;for(let k=0;k<LY.lines.length;k++){if(LY.lines[k].t<=t+.25)i=k;else break}
  if(i===LY.idx)return;LY.idx=i;
  document.querySelectorAll(".ly p").forEach((p,k)=>{p.classList.toggle("on",k===i);p.classList.toggle("past",k<i)});
  if(i>=0&&performance.now()-lyUserScroll>4000)document.querySelector(`.ly p[data-i="${i}"]`)?.scrollIntoView({behavior:"smooth",block:"center"});
}
["touchmove","wheel"].forEach(ev=>$("#sheet").addEventListener(ev,()=>lyUserScroll=performance.now(),{passive:true}));
