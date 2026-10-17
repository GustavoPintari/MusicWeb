// Retrospective (recap) of a month or a year.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- retrospective: a month or a year of listening (radio is not included)
const RT={periods:null,period:null,data:null};
const hm=sec=>{const h=Math.floor(sec/3600),m=Math.round(sec%3600/60);return h?`${h}h ${m}min`:`${m}min`};
const plural=(n,one,many)=>n===1?T(one):T(many);       // singular/plural label
function monthLabel(id,capital=true){
  const [y,m]=id.split("-"),s=new Date(+y,+m-1,1).toLocaleDateString(LOC,{month:"long",year:"numeric"});
  return capital?s.charAt(0).toUpperCase()+s.slice(1):s;
}
// previous period, as it reads mid-sentence ("... em relação a setembro de 2026")
const prevLabel=id=>id.length===4?String(+id-1):monthLabel((([y,m])=>m===1?`${y-1}-12`:`${y}-${String(m-1).padStart(2,"0")}`)(id.split("-").map(Number)),false);
async function renderRetro(){
  if($("#rtsh"))return drawRetro();
  $("#sheetBody").innerHTML=`<div id="rtsh"><h1>${T("Retrospectiva")}</h1>
    <select id="rtsel" aria-label="${T("Período")}"></select><div id="rtbody"><p class="empty">${T("Carregando…")}</p></div></div>`;
  try{RT.periods=await (await fetch("/api/retro")).json()}catch(e){$("#rtbody").innerHTML=`<p class="empty">${T("Sem conexão com o servidor")}</p>`;return}
  const ms=RT.periods.months,ys=RT.periods.years;
  if(!ms.length){$("#rtsel").hidden=true;$("#rtbody").innerHTML=`<p class="empty">${T("Nada tocado ainda.")}</p>`;return}
  const now=new Date(),cur=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;
  $("#rtsel").innerHTML=`<optgroup label="${T("Meses")}">${ms.map(m=>`<option value="${m.id}">${monthLabel(m.id)}</option>`).join("")}</optgroup>
    <optgroup label="${T("Anos")}">${ys.map(y=>`<option value="${y.id}">${y.id}</option>`).join("")}</optgroup>`;
  if(![...ms,...ys].some(x=>x.id===RT.period))RT.period=ms.some(m=>m.id===cur)?cur:ms[0].id;
  $("#rtsel").value=RT.period;loadRetro();
}
async function loadRetro(){
  RT.data=null;drawRetro();
  try{RT.data=await (await fetch("/api/retro?period="+RT.period)).json()}catch(e){RT.data={error:true}}
  if(openAlbum==="@retro")drawRetro();
}
function bars(values,labels,axis,title){         // one series, so no legend: the title names it
  const max=Math.max(...values,1),pk=values.indexOf(Math.max(...values));
  return `<div class="bars" role="img" aria-label="${esc(title)}">${values.map((v,i)=>`<div class="b${i===pk&&v?" pk":""}" title="${esc(labels[i])}: ${T("{n} reproduções",{n:v})}">${i===pk&&v?`<span>${v}</span>`:""}<i style="height:${Math.round(v/max*90)}px"></i></div>`).join("")}</div>
    <div class="axis">${axis.map(a=>`<span>${esc(a)}</span>`).join("")}</div>
    <table class="sr"><caption>${esc(title)}</caption>${values.map((v,i)=>`<tr><th>${esc(labels[i])}</th><td>${v}</td></tr>`).join("")}</table>`;
}
function drawRetro(){
  const box=$("#rtbody");if(!box)return;
  const d=RT.data;
  if(!d){box.innerHTML=`<p class="empty">${T("Carregando…")}</p>`;return}
  if(d.error||!d.ok){box.innerHTML=`<p class="empty">${T("Sem conexão com o servidor")}</p>`;return}
  if(!d.plays){box.innerHTML=`<p class="empty">${T("Nada tocado neste período.")}</p>`;return}
  const tiles=[[hm(d.seconds),T("ouvindo música")],[d.plays,plural(d.plays,"reprodução","reproduções")],[d.tracks,plural(d.tracks,"música diferente","músicas diferentes")],
    [d.artists,plural(d.artists,"artista","artistas")],[d.days,plural(d.days,"dia com música","dias com música")],
    [d.streak,plural(d.streak,"dia seguido (recorde)","dias seguidos (recorde)")],[d.new_artists,plural(d.new_artists,"artista novo","artistas novos")]];
  const pv=d.previous,pct=pv.seconds?Math.round((d.seconds-pv.seconds)/pv.seconds*100):null;
  const top=d.top_tracks[0],cv=x=>x.cover?cover({id:x.cover,name:x.title||x.album,artist:x.artist,cv:byId[x.cover]?.cv}):cover({id:"x",name:x.title||x.album,artist:x.artist}).replace(/<img[^>]*>/,"");
  const hl=h=>LANG==="en"?new Date(2000,0,1,h).toLocaleTimeString("en-US",{hour:"numeric"}):`${h}h`;
  const wd=(i,f)=>new Date(2024,0,1+i).toLocaleDateString(LOC,{weekday:f});      // 2024-01-01 was a Monday (server: 0 = Monday)
  const ph=d.hours.indexOf(Math.max(...d.hours)),pw=d.weekdays.indexOf(Math.max(...d.weekdays));
  box.innerHTML=`<div class="rt-hero">${tiles.map(([v,l])=>`<div class="tile"><b>${esc(v)}</b><small>${l}</small></div>`).join("")}</div>
    ${pct!==null?`<p class="rt-cmp">${T("{pct} de tempo ouvindo em relação a {period}",{pct:(pct>=0?"+":"")+pct+"%",period:prevLabel(d.period)})}</p>`:""}
    <div class="rt-top hr${top.available?"":" gone"}" data-h="${esc(top.id)}">${cv(top)}<div><small>${T("Música do período")}</small><b>${esc(top.title)}</b>
      <small>${esc(top.artist)} · ${T("{n} vezes",{n:top.count})}</small></div></div>
    <div class="sec">${T("Músicas mais tocadas")}</div>${d.top_tracks.map((x,i)=>playRow(x,i+1,`${x.count}×`)).join("")}
    <div class="sec">${T("Artistas mais ouvidos")}</div>${d.top_artists.map((a,i)=>`<div class="hr" style="cursor:default"><span class="n">${i+1}</span>
      <span class="ti"><b>${esc(a.artist)}</b><small>${T("{n} reproduções",{n:a.count})} · ${hm(a.seconds)}</small></span></div>`).join("")}
    ${d.top_albums.length?`<div class="sec">${T("Álbuns mais ouvidos")}</div><div class="rt-albums">${d.top_albums.map(a=>`<div>${cv(a)}<b>${esc(a.album)}</b><small>${esc(a.artist)} · ${a.count}×</small></div>`).join("")}</div>`:""}
    <div class="sec">${T("Quando você ouve")}</div>
    <div class="chart"><p>${T("Horário com mais músicas: {h}",{h:hl(ph)})}</p>
      ${bars(d.hours,d.hours.map((_,h)=>hl(h)),d.hours.map((_,h)=>h%6===0?hl(h):""),T("Reproduções por hora do dia"))}</div>
    <div class="chart"><p>${T("Dia com mais músicas: {d}",{d:wd(pw,"long")})}</p>
      ${bars(d.weekdays,d.weekdays.map((_,i)=>wd(i,"long")),d.weekdays.map((_,i)=>wd(i,"short")),T("Reproduções por dia da semana"))}</div>`;
  markPlaying();
}
