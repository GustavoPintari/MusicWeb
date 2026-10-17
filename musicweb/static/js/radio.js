// Internet radio (Radio Browser): stations as tracks, search, favorites and recent.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- radio stations: each one is a single live "track"
let regionNames=null;try{regionNames=new Intl.DisplayNames([LOC],{type:"region"})}catch(e){}
const countryName=st=>{try{return st.countrycode&&regionNames?.of(st.countrycode)||st.country}catch(e){return st.country}};   // "Brazil" -> "Brasil"
const radioKnown={};
function regRadio(st){
  radioKnown[st.id]=st;
  const t={id:st.id,title:st.title,artist:"",dur:0,fmt:st.fmt,q:st.q,n:0,disc:1,url:st.path,hls:st.hls,radio:true,country:countryName(st)};
  const a={id:st.id,name:st.title,full:st.title,artist:countryName(st),year:"",cv:0,radio:true,tracks:[t]};
  trackById[st.id]={t,a};return a;
}
async function loadRadios(){                // favorites and recent stations, so they can be shown/played after a reload
  try{const d=await (await fetch("/api/radio")).json();R.data=d;[...d.favorites,...d.recent].forEach(regRadio)}catch(e){}
}

// ---------- radio screen: search Radio Browser by name / country / genre; favorites and recent
const R={data:null,results:null,tag:""};
function renderRadio(){
  if($("#rdsh"))return radioLists();
  $("#sheetBody").innerHTML=`<div id="rdsh"><h1>${T("Rádios")}</h1>
    <form id="rdf"><input id="rdq" type="search" placeholder="${T("Buscar rádio pelo nome…")}" autocomplete="off" enterkeyhint="search">
      <select id="rdc" aria-label="${T("País")}"><option value="">${T("Todos os países")}</option></select>
      <button class="big">${T("Buscar")}</button></form>
    <div id="rdtags" class="pas"></div><div id="rderr"></div>
    <div id="rdlists"><p class="empty">${T("Carregando…")}</p></div>
    <p class="note" style="margin-top:22px">${T("Catálogo de rádios: Radio Browser (radio-browser.info)")}</p></div>`;
  radioInit();
}
async function radioInit(){
  try{
    const get=u=>fetch(u).then(r=>{if(!r.ok)throw new Error();return r.json()});
    const [ov,cs,tg]=await Promise.all([get("/api/radio"),get("/api/radio/countries"),get("/api/radio/tags")]);
    if(!$("#rdsh"))return;
    R.data=ov;[...ov.favorites,...ov.recent].forEach(regRadio);
    const opts=cs.map(c=>({...c,label:countryName({countrycode:c.code,country:c.name})})).sort((a,b)=>a.label.localeCompare(b.label,LOC));
    $("#rdc").insertAdjacentHTML("beforeend",opts.map(c=>`<option value="${c.code}">${esc(c.label)} (${c.count})</option>`).join(""));
    $("#rdc").value=ov.filters.country||"";            // last choice, saved by the server (first time: all countries)
    R.tag=ov.filters.tag||"";
    $("#rdtags").innerHTML=tg.map(t=>`<button class="pa${t===R.tag?" on":""}" data-tag="${esc(t)}">${esc(t)}</button>`).join("");
    radioSearch();
  }catch(e){if($("#rdlists"))$("#rdlists").innerHTML=`<p class="empty">${T("Não consegui falar com o Radio Browser")}</p>`}
}
async function radioSearch(){
  if(!$("#rdsh"))return;
  const q=$("#rdq").value.trim(),country=$("#rdc").value;
  $("#rderr").textContent="";R.results=null;radioLists();
  try{
    const r=await fetch("/api/radio/search?"+new URLSearchParams({q,country,tag:R.tag})),d=await r.json();
    if(!r.ok)throw new Error(d.error);
    R.results=d;
  }catch(e){R.results=[];$("#rderr").textContent=e.message||T("Não consegui falar com o Radio Browser")}
  if(openAlbum==="@radio")radioLists();
}
function radioRow(st,favs){
  const fav=favs.has(st.uuid),sub=[countryName(st),(st.tags||[]).slice(0,3).join(", "),[st.fmt,st.q].filter(Boolean).join(" ")].filter(Boolean).join(" · ");
  const logo=`<div class="cv" style="--ph:hsl(${hue(st.title)} 35% 28%)">${esc((st.title.match(/[\p{L}\p{N}]/u)||["♪"])[0].toUpperCase())}${st.favicon?`<img loading="lazy" src="${esc(st.favicon)}" referrerpolicy="no-referrer" onload="this.classList.add('ok')" onerror="this.remove()" alt="">`:""}</div>`;
  return `<div class="hr rr" data-r="${st.uuid}">${logo}<span class="ti"><b>${esc(st.title)}</b><small>${esc(sub)}</small></span>
    <button class="star${fav?" on":""}" data-fav="${st.uuid}" title="${fav?T("Tirar dos favoritos"):T("Favoritar")}">${fav?"★":"☆"}</button></div>`;
}
function radioLists(){
  if(!$("#rdlists"))return;
  const d=R.data||{favorites:[],recent:[]},favs=new Set(d.favorites.map(f=>f.uuid)),rec=d.recent.filter(st=>!favs.has(st.uuid)).slice(0,6);
  const filtered=R.tag||$("#rdc").value||$("#rdq").value.trim();
  $("#rdlists").innerHTML=
    (d.favorites.length?`<div class="sec">${T("Favoritas")}</div>`+d.favorites.map(st=>radioRow(st,favs)).join(""):"")+
    (rec.length?`<div class="sec">${T("Ouvidas recentemente")}</div>`+rec.map(st=>radioRow(st,favs)).join(""):"")+
    `<div class="sec">${filtered?T("Resultados"):T("Mais populares")}</div>`+
    (!R.results?`<p class="empty">${T("Buscando…")}</p>`:R.results.length?R.results.map(st=>radioRow(st,favs)).join(""):`<p class="empty">${T("Nenhuma rádio encontrada.")}</p>`);
  markPlaying();
}
async function playRadio(uuid,el){
  el.classList.add("busy");navigator.vibrate?.(10);
  try{
    const r=await (await fetch("/api/radio/select",{method:"POST",body:JSON.stringify({uuid})})).json();
    if(!r.ok)throw new Error(r.error);
    regRadio(r.station);
    if(R.data)R.data.recent=[r.station,...R.data.recent.filter(x=>x.uuid!==uuid)];
    await ctl.playTrack(r.station.id);radioLists();
  }catch(e){toast(e.message||T("Sem conexão com o servidor"),6000)}
  finally{el.classList.remove("busy")}
}
async function toggleFav(uuid,btn){
  const on=!btn.classList.contains("on");
  try{
    const r=await (await fetch("/api/radio/favorite",{method:"POST",body:JSON.stringify({uuid,on})})).json();
    if(!r.ok)throw new Error(r.error);
    if(R.data)R.data.favorites=r.favorites;r.favorites.forEach(regRadio);radioLists();
    toast(on?T("Adicionada aos favoritos"):T("Removida dos favoritos"));
  }catch(e){toast(e.message||T("Sem conexão com o servidor"))}
}
