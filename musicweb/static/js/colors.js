// Album colors taken from the cover, and the album page background (glass / vinyl).
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- album colors from the cover: up to three strong hues (for a gradient of color "patches"),
// darkened to sit behind white text, plus a light accent of the same hue for the buttons.
// Hues are grouped in 24 bins weighted by saturation, so a few vivid colors win over a large white or gray area,
// and the colors aren't averaged together (averaging many hues is what made "muddy brown").
const tintCache={};
function toHsl(r,g,b){
  r/=255;g/=255;b/=255;const mx=Math.max(r,g,b),mn=Math.min(r,g,b),l=(mx+mn)/2,dl=mx-mn;
  let h=0;if(dl)h=(mx===r?((g-b)/dl+6)%6:mx===g?(b-r)/dl+2:(r-g)/dl+4)*60;
  return [h,dl?dl/(1-Math.abs(2*l-1)):0,l];
}
function coverColors(d){                    // d: RGBA pixels of the cover, scaled down
  const bins=Array.from({length:24},()=>({w:0,r:0,g:0,b:0}));let n=0,cn=0;
  for(let i=0;i<d.length;i+=4){
    if(d[i+3]<128)continue;n++;
    const [h,s,l]=toHsl(d[i],d[i+1],d[i+2]);
    if(s<.2||l<.12||l>.9)continue;          // grays, near black/white
    cn++;
    const wt=s*s*Math.max(.05,1-Math.abs(l-.5)*1.6),bn=bins[Math.floor(h/15)%24];   // favor vivid mid tones
    bn.w+=wt;bn.r+=d[i]*wt;bn.g+=d[i+1]*wt;bn.b+=d[i+2]*wt;
  }
  if(!n||cn<n*.03)return null;              // black and white cover
  const at=i=>bins[(i+24)%24],score=i=>at(i-1).w*.5+at(i).w+at(i+1).w*.5;
  const hueOf=k=>{let w=0,r=0,g=0,b=0;for(const bn of [at(k-1),at(k),at(k+1)]){w+=bn.w;r+=bn.r;g+=bn.g;b+=bn.b}return toHsl(r/w,g/w,b/w)};
  // strongest hue first; each next one at least 45° from the others and with 8% of the first one's weight
  const far=(i,ks)=>ks.every(k=>Math.min(Math.abs(i-k),24-Math.abs(i-k))>=3),ks=[];
  while(ks.length<3){
    let b=-1;for(let i=0;i<24;i++)if(far(i,ks)&&(b<0||score(i)>score(b)))b=i;
    if(b<0||score(b)<=0||(ks.length&&score(b)<score(ks[0])*.08))break;
    ks.push(b);
  }
  const cl=(v,a,z)=>Math.min(z,Math.max(a,v));
  const dark=([h,s])=>`hsl(${Math.round(h)} ${Math.round(cl(s*1.1,.45,.8)*100)}% ${h>=40&&h<=75?24:28}%)`;   // yellows look brighter
  const cs=ks.map(k=>dark(hueOf(k))),[h,s]=hueOf(ks[0]);
  return {bg:cs[0],bg2:cs[1]||cs[0],bg3:cs[2]||cs[1]||cs[0],
    vbg:`hsl(${Math.round(h)} ${Math.round(cl(s,.35,.6)*100)}% 20%)`,groove:`hsl(${Math.round(h)} ${Math.round(cl(s*1.2,.5,.85)*100)}% 55%)`,
    ac:`hsl(${Math.round(h)} ${Math.round(cl(s,.6,.9)*100)}% ${h>=200&&h<=280?72:64}%)`};
}
function albumTint(a){
  if(tintCache[a.id])return Promise.resolve(tintCache[a.id]);
  const ph=`hsl(${hue((a.name||"")+(a.artist||""))} 35% 26%)`,gray={bg:"hsl(0 0% 17%)",bg2:"hsl(0 0% 17%)",bg3:"hsl(0 0% 17%)",vbg:"#1b1b1d",groove:"#8a8a8a",ac:""};
  return new Promise(res=>{
    const img=new Image();
    img.onload=()=>{
      try{
        const c=document.createElement("canvas");c.width=c.height=48;
        const x=c.getContext("2d");x.drawImage(img,0,0,48,48);
        res(tintCache[a.id]=coverColors(x.getImageData(0,0,48,48).data)||gray);
      }catch(e){res(tintCache[a.id]={bg:ph,bg2:ph,bg3:ph,vbg:ph,groove:"#8a8a8a",ac:""})}
    };
    img.onerror=()=>res(tintCache[a.id]={bg:ph,bg2:ph,bg3:ph,vbg:ph,groove:"#8a8a8a",ac:""});   // same hue as the placeholder cover
    img.src=`/api/cover/${a.id}?v=${a.cv||0}`;
  });
}
function paint(el,c,pre){                   // c.ac is empty for gray covers: keep the default accent
  el.style.setProperty(`--${pre}`,c.bg);el.style.setProperty(`--${pre}2`,c.bg2);el.style.setProperty(`--${pre}3`,c.bg3);
  if(c.ac)el.style.setProperty("--ac",c.ac);else el.style.removeProperty("--ac");
}
// key: which sheet asked, so a late answer can't tint another one. The player bar takes the same colors,
// so the album page looks like one piece; everywhere else both stay neutral.
function setTint(key,a){
  const sh=$("#sheet"),bar=$("#bar"),meta=document.querySelector('meta[name="theme-color"]');
  sh.classList.toggle("isalbum",!!a);
  if(!a){for(const el of [sh,bar]){el.classList.remove("tinted");el.style.removeProperty("--ac")}meta.content="#121212";return}
  albumTint(a).then(c=>{
    if(openAlbum!==key)return;
    paint(sh,c,"tint");paint(bar,c,"btint");
    sh.style.setProperty("--vbg",c.vbg);sh.style.setProperty("--groove",c.groove);
    sh.style.setProperty("--cvurl",`url("/api/cover/${a.id}?v=${a.cv||0}")`);
    sh.classList.add("tinted");bar.classList.add("tinted");meta.content=albumBg==="vinyl"?c.vbg:c.bg;
  });
}


let albumBg="glass";try{albumBg=localStorage.getItem("albumbg")==="vinyl"?"vinyl":"glass"}catch(e){}
function setAlbumBg(v){
  albumBg=v;$("#sheet").dataset.bg=v;
  document.querySelectorAll("#bgsw button").forEach(b=>b.classList.toggle("on",b.dataset.bg===v));
  try{localStorage.setItem("albumbg",v)}catch(e){}
  grooveCenter();
}
function grooveCenter(){                    // the vinyl grooves come out from the middle of the album cover
  const sh=$("#sheet"),cv=sh.querySelector(".hero .cv");if(!cv)return;
  const r=cv.getBoundingClientRect(),o=sh.getBoundingClientRect();
  sh.style.setProperty("--gx",Math.round(r.left-o.left+r.width/2)+"px");
  sh.style.setProperty("--gy",Math.round(r.top-o.top+sh.scrollTop+r.height/2)+"px");
}
