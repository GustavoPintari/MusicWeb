// "Tocadas": most played tracks/artists and play history.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- played: most played tracks/artists and history (stored by the server in SQLite)
let historyOn=true,playMin=30;
const P={days:30,data:null,loading:false};
try{const v=localStorage.getItem("pdays");if(v!=null)P.days=+v}catch(e){}
async function loadPlays(){
  P.loading=true;
  try{P.data=await (await fetch("/api/stats?days="+P.days)).json()}catch(e){P.data={error:true}}
  P.loading=false;if(view==="plays")renderPlays();
}
function relTime(at){
  const d=new Date(at*1000),now=new Date(),s=(now-d)/1000,hm=d.toLocaleTimeString(LOC,{hour:"2-digit",minute:"2-digit"});
  if(s<60)return T("agora");
  if(s<3600)return T("há {n} min",{n:Math.floor(s/60)});
  const day=x=>new Date(x.getFullYear(),x.getMonth(),x.getDate()).getTime(),dd=(day(now)-day(d))/86400000;
  if(dd===0)return T("hoje {hm}",{hm});
  if(dd===1)return T("ontem {hm}",{hm});
  return `${d.toLocaleDateString(LOC,{day:"2-digit",month:"2-digit"})} ${hm}`;
}
function playRow(x,left,right){
  const c=x.cover?cover({id:x.cover,name:x.title,artist:x.artist,cv:byId[x.cover]?.cv}):cover({id:"x",name:x.title,artist:x.artist}).replace(/<img[^>]*>/,"");
  return `<div class="hr${x.available?"":" gone"}" data-h="${esc(x.id)}" title="${x.available?"":T("Não está mais na biblioteca")}"><span class="n">${left}</span>${c}
    <span class="ti"><b>${esc(x.title)}</b><small>${esc(x.artist)}${x.album?" · "+esc(x.album):""}</small></span><span class="d">${right}</span></div>`;
}
function renderPlays(){
  const d=P.data;
  if(!d){$("#lib").innerHTML=`<p class="empty">${T("Carregando…")}</p>`;if(!P.loading)loadPlays();return}
  if(d.error){$("#lib").innerHTML=`<p class="empty">${T("Sem conexão com o servidor")}</p>`;return}
  if(!d.enabled){$("#lib").innerHTML=`<p class="empty">${T("O histórico está desligado ([history] enabled no config.toml).")}</p>`;return}
  const q=$("#q").value.trim().toLowerCase(),f=x=>!q||[x.title,x.artist,x.album].some(v=>v.toLowerCase().includes(q));
  const per=`<div class="per">${[[7,T("7 dias")],[30,T("30 dias")],[0,T("Sempre")]].map(([v,l])=>`<button data-days="${v}" class="${v===P.days?"on":""}">${l}</button>`).join("")}
    <button class="pa" id="rtb">${T("Retrospectiva")}</button>
    <span>${d.total} ${d.total===1?T("reprodução"):T("reproduções")}</span></div>`;
  if(!d.recent.length){$("#lib").innerHTML=per+`<p class="empty">${T("Nada tocado ainda.")}<br>${T("Uma música entra aqui depois de {n} s ouvindo.",{n:playMin})}</p>`;return}
  const top=d.top_tracks.filter(f),rec=d.recent.filter(f);
  $("#lib").innerHTML=per+
    `<div class="sec">${T("Mais tocadas")}</div>`+(top.length?top.map((x,i)=>playRow(x,i+1,`${x.count}×`)).join(""):`<p class="empty" style="margin-top:8px">${T("Nada neste período.")}</p>`)+
    (d.top_artists.length&&!q?`<div class="sec">${T("Artistas mais ouvidos")}</div><div class="pas">${d.top_artists.map(a=>`<button class="pa" data-artist="${esc(a.artist)}">${esc(a.artist)}<small>${a.count}</small></button>`).join("")}</div>`:"")+
    `<div class="sec">${T("Histórico")}</div>`+rec.map(x=>playRow(x,"",relTime(x.at))).join("");
  markPlaying();
}
async function playFromHistory(id,el){
  el.classList.add("busy");
  try{
    if(!trackById[id]){toast(T("Essa faixa não está mais na biblioteca"));return}
    await ctl.playTrack(id);
  }catch(e){toast(e.message,6000)}
  finally{el.classList.remove("busy")}
}
