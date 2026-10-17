// Library: album grid, artists, the album page, editing tags, covers and removing an album.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

function matches(a,q){return !q||a.name.toLowerCase().includes(q)||a.full.toLowerCase().includes(q)||a.artist.toLowerCase().includes(q)||a.tracks.some(t=>t.title.toLowerCase().includes(q))}
function card(a){const cur=S.track&&S.track.album===a.id;
  const af=albumFmt(a);
  return `<div class="al${cur?" on":""}" data-a="${a.id}">${cover(a).replace('">',`">${af.f?`<span class="fb${LOSSLESS.has(af.f)?" hq":""}">${esc(af.f)}</span>`:""}`)}<b>${esc(a.name)}</b><small>${esc(view==="albums"?a.artist:"")}${view==="albums"&&a.year?" · ":""}${esc(a.year)}</small></div>`}

function render(){
  document.querySelectorAll(".seg button").forEach(b=>b.classList.toggle("on",b.dataset.v===view));
  if(view==="plays")return renderPlays();
  const q=$("#q").value.trim().toLowerCase(), list=lib.filter(a=>matches(a,q));
  if(!list.length){$("#lib").innerHTML=`<p class="empty">${lib.length?T("Nada encontrado"):T("Nenhuma música encontrada")}</p>`;return}
  if(view==="albums"){
    $("#lib").innerHTML=`<div class="grid">${[...list].sort((a,b)=>a.name.localeCompare(b.name,LOC)).map(card).join("")}</div>`;
  }else{
    const ar={};list.forEach(a=>(ar[a.artist]??=[]).push(a));
    $("#lib").innerHTML=Object.keys(ar).sort((a,b)=>a.localeCompare(b,LOC)).map(n=>{
      const as=ar[n].sort((a,b)=>(a.year||"9999").localeCompare(b.year||"9999")),open=q||openArtists.has(n);
      return `<div class="ar${open?" open":""}" data-ar="${esc(n)}"><button>${cover({id:"x",name:n,artist:""},"av").replace(/<img[^>]*>/,"")}
        <span class="nm">${esc(n)}<small>${as.length} ${as.length>1?T("álbuns"):T("álbum")} · ${T("{n} faixas",{n:as.reduce((s,a)=>s+a.tracks.length,0)})}</small></span>
        <svg class="chev" viewBox="0 0 24 24"><path d="M10 6 8.6 7.4 13.2 12l-4.6 4.6L10 18l6-6z"/></svg></button>
        <div class="row">${as.map(card).join("")}</div></div>`}).join("");
  }
}

let editing=false;
function renderSheet(){
  if(openAlbum==="@radio"){setTint();return renderRadio()}
  if(openAlbum==="@retro"){setTint();return renderRetro()}
  if(openAlbum==="@ly"){setTint();return renderLyrics()}
  const a=byId[openAlbum];if(!a)return;
  setTint(openAlbum,a);
  if(editing)return renderEdit(a);
  const af=albumFmt(a),tot=a.tracks.reduce((s,t)=>s+(t.dur||0),0),discs=new Set(a.tracks.map(t=>t.disc)).size>1;let lastDisc=null;
  $("#sheetBody").innerHTML=`<div class="hero">${cover(a,"",true)}<div class="inf">
      <h1>${esc(a.name)}</h1>
      ${a.full!==a.name?`<div class="full">${esc(a.full)}</div>`:""}
      <div class="meta">${esc(a.artist)}${a.year?" · "+esc(a.year):""} · ${T("{n} faixas",{n:a.tracks.length})}${tot?" · "+fmt(tot):""} ${af.mixed?`<span class="fb">${esc(af.f)}</span>`:fmtBadge(af.f,af.q)}</div>
      <div class="acts"><button class="big" id="playAll">${PLAY} ${T("Tocar álbum")}</button><a class="btn2" id="dlAlbum" href="/api/download/${a.id}" download>${T("Baixar")}</a><button id="editAlbum">${T("Editar")}</button></div></div></div>`+
    a.tracks.map(t=>{const d=discs&&t.disc!==lastDisc?`<div class="disc">${T("Disco {n}",{n:t.disc})}</div>`:"";lastDisc=t.disc;
      return d+`<div class="t" data-t="${t.id}"><span class="n">${t.n||""}</span><span class="ti">${esc(t.title)}${t.artist&&t.artist!==a.artist?`<small>${esc(t.artist)}</small>`:""}</span>${af.mixed?fmtBadge(t.fmt):""}<span class="d">${t.dur?fmt(t.dur):""}</span></div>`}).join("");
  markPlaying();
}

function renderEdit(a){
  $("#sheetBody").innerHTML=`<div class="ed"><div class="hero">${cover(a,"",true)}<div class="inf"><h1>${T("Editar álbum")}</h1><div class="meta">${esc(a.full)}</div>
      <div class="cvacts"><label class="btn">${T("Enviar imagem")}<input type="file" id="e_file" accept="image/*" hidden></label>
        <button id="e_find">${T("Buscar capa")}</button></div></div></div>
    <div id="cs"><form id="csf"><input id="csq" value="${esc((a.artist===T("Desconhecido")||a.artist===T("Vários artistas")?"":a.artist+" ")+a.name)}"><button>${T("Buscar")}</button></form>
      <div id="csr"></div></div>
    <label>${T("Nome do álbum")}</label><input id="e_album" value="${esc(a.full)}">
    <div class="two"><div><label>${T("Artista do álbum")}</label><input id="e_aa" value="${esc(a.artist)}"></div>
      <div><label>${T("Ano")}</label><input id="e_year" inputmode="numeric" value="${esc(a.year)}"></div></div>
    <label style="margin-top:18px">${T("Faixas (nº, título e artista)")}</label>
    ${a.tracks.map(t=>`<div class="et" data-t="${t.id}"><input class="num" inputmode="numeric" value="${t.n||""}" aria-label="${T("Número")}">
      <input class="ti" value="${esc(t.title)}" aria-label="${T("Título")}"><input class="ar" value="${esc(t.artist)}" placeholder="${T("Artista da faixa")}" aria-label="${T("Artista")}"></div>`).join("")}
    <p class="note">${T("As alterações são gravadas nas tags dos arquivos de música.")}</p>
    <div class="errs" id="e_err"></div>
    <div class="acts"><button class="big" id="e_save">${T("Salvar")}</button><button id="e_cancel">${T("Cancelar")}</button></div>
    <div class="danger"><button id="e_del">${T("Remover álbum")}</button>
      <div id="delbox"><p>${T("Remover")} <b>${esc(a.full)}</b> (${a.tracks.length} ${a.tracks.length>1?T("faixas"):T("faixa")})?
        ${T("Os arquivos vão para a lixeira e podem ser recuperados.")}</p>
        <label><input type="checkbox" id="e_perm"> ${T("Apagar definitivamente (não dá para desfazer)")}</label>
        <div class="acts"><button class="redbtn" id="e_delok">${T("Remover")}</button><button id="e_delno">${T("Cancelar")}</button></div></div></div></div>`;
}

async function saveEdit(btn){
  const a=byId[openAlbum],v=id=>$(id).value.trim(),body={album:a.id,fields:{},tracks:{}};
  if(v("#e_album")!==a.full)body.fields.album=v("#e_album");
  if(v("#e_aa")!==a.artist)body.fields.albumartist=v("#e_aa");
  if(v("#e_year")!==a.year)body.fields.date=v("#e_year");
  document.querySelectorAll(".et").forEach(r=>{
    const t=a.tracks.find(x=>x.id===r.dataset.t),c={},val=s=>r.querySelector(s).value.trim();
    if(val(".num")!==String(t.n||""))c.tracknumber=val(".num");
    if(val(".ti")!==t.title)c.title=val(".ti");
    if(val(".ar")!==(t.artist||""))c.artist=val(".ar");
    if(Object.keys(c).length)body.tracks[t.id]=c;
  });
  if(!body.fields.album&&body.fields.album!==undefined){$("#e_err").textContent=T("O nome do álbum não pode ficar vazio.");return}
  if(!Object.keys(body.fields).length&&!Object.keys(body.tracks).length){editing=false;renderSheet();return}
  btn.classList.add("busy");btn.disabled=true;navigator.vibrate?.(10);
  try{
    const r=await (await fetch("/api/edit",{method:"POST",body:JSON.stringify(body)})).json();
    if(r.album)openAlbum=r.album;
    if(!r.ok){$("#e_err").textContent=T("Algumas alterações falharam:")+"\n"+r.errors.join("\n");await load();return}
    editing=false;await load();
  }catch(e){$("#e_err").textContent=T("Sem conexão com o servidor")}
  finally{btn.classList.remove("busy");btn.disabled=false}
}

async function afterCoverChange(){
  await load();const a=byId[openAlbum];
  if(a){const old=document.querySelector(".ed .hero .cv");if(old)old.outerHTML=cover(a,"",true)}
  toast(T("Capa atualizada"));
}

function shrinkImage(file,max=1200){       // shrink large photos before uploading
  return new Promise((res,rej)=>{
    const img=new Image(),url=URL.createObjectURL(file);
    img.onload=()=>{const k=Math.min(1,max/Math.max(img.width,img.height)),c=document.createElement("canvas");
      c.width=Math.round(img.width*k);c.height=Math.round(img.height*k);c.getContext("2d").drawImage(img,0,0,c.width,c.height);
      URL.revokeObjectURL(url);c.toBlob(b=>b?res(b):rej(new Error(T("falha ao converter"))),"image/jpeg",.9)};
    img.onerror=()=>{URL.revokeObjectURL(url);rej(new Error(T("não consegui abrir a imagem")))};
    img.src=url;
  });
}

async function uploadCover(file){
  const lbl=document.querySelector("label.btn");lbl.classList.add("busy");
  try{
    const blob=await shrinkImage(file);
    const r=await (await fetch("/api/cover_upload?album="+openAlbum,{method:"POST",body:blob})).json();
    if(!r.ok)throw new Error(r.error);
    await afterCoverChange();
  }catch(e){toast(T("Erro ao enviar a capa: ")+e.message,6000)}
  finally{lbl.classList.remove("busy")}
}

async function searchCovers(){
  const q=$("#csq").value.trim();if(!q)return;
  $("#csr").innerHTML=`<small style="grid-column:1/-1;color:var(--mut)">${T("Buscando…")}</small>`;
  try{
    const list=await (await fetch("/api/cover_search?q="+encodeURIComponent(q))).json();
    $("#csr").innerHTML=list.length?list.map((c,i)=>`<div class="c" data-i="${i}"><img src="${esc(c.thumb)}" loading="lazy" alt=""><small>${esc(c.title)}</small><small>${esc(c.artist)} · ${c.src}</small></div>`).join(""):`<small style="grid-column:1/-1">${T("Nada encontrado. Tente outro termo.")}</small>`;
    $("#csr")._list=list;
  }catch(e){$("#csr").innerHTML=`<small style="grid-column:1/-1;color:var(--err)">${T("Sem conexão com o servidor")}</small>`}
}

async function pickCover(el){
  const c=$("#csr")._list[+el.dataset.i];el.classList.add("busy");navigator.vibrate?.(10);
  try{
    const r=await (await fetch("/api/cover_set",{method:"POST",body:JSON.stringify({album:openAlbum,url:c.url})})).json();
    if(!r.ok)throw new Error(r.error);
    $("#cs").classList.remove("open");await afterCoverChange();
  }catch(e){toast(T("Erro ao trocar a capa: ")+e.message,6000)}
  finally{el.classList.remove("busy")}
}

async function deleteAlbum(btn){
  const permanent=$("#e_perm").checked,name=byId[openAlbum]?.full;
  btn.classList.add("busy");btn.disabled=true;
  try{
    const r=await (await fetch("/api/delete",{method:"POST",body:JSON.stringify({album:openAlbum,permanent})})).json();
    if(!r.ok){toast(T("Alguns arquivos não foram removidos:")+"\n"+r.errors.join("\n"),8000)}
    else toast(permanent?T('"{name}" apagado',{name}):T('"{name}" movido para a lixeira',{name}));
    editing=false;history.back();await load();
  }catch(e){toast(T("Sem conexão com o servidor"))}
  finally{btn.classList.remove("busy");btn.disabled=false}
}
