// Interface language: Portuguese text is the key, EN maps it to English.
// Plain script (no modules): the files share one global scope and load in order (see index.html).

// ---------- interface language: the server sets <html lang> from [interface] language in config.toml.
// Portuguese text is the key; EN maps it to English. T("{n} faixas",{n:3}) fills placeholders.
const LANG=document.documentElement.lang.toLowerCase().startsWith("en")?"en":"pt-BR",LOC=LANG==="en"?"en-US":"pt-BR";
const EN={
  "Buscar álbum, artista ou faixa…":"Search albums, artists or tracks…","Álbuns":"Albums","Artistas":"Artists","Tocadas":"Played",
  "Reescanear biblioteca":"Rescan library","‹ Voltar":"‹ Back","Letra da música":"Lyrics",
  "Anterior":"Previous","Tocar/Pausar":"Play/Pause","Próxima":"Next","Volume":"Volume","Parar":"Stop","Diminuir volume":"Volume down","Aumentar volume":"Volume up",
  "Visualizador":"Visualizer","Agulhas":"Needles","Morros":"Hills","Desligado":"Off",
  "Sem conexão com o servidor":"No connection to the server","Erro na página: ":"Page error: ",
  "Nada encontrado":"Nothing found","Nenhuma música encontrada":"No music found","álbum":"album","álbuns":"albums","faixa":"track","faixas":"tracks","{n} faixas":"{n} tracks",
  "Tocar álbum":"Play album","Baixar":"Download","Editar":"Edit","Disco {n}":"Disc {n}",
  "Desconhecido":"Unknown","Vários artistas":"Various artists",
  "Editar álbum":"Edit album","Enviar imagem":"Upload image","Buscar capa":"Find cover","Buscar":"Search","Nome do álbum":"Album name",
  "Artista do álbum":"Album artist","Ano":"Year","Faixas (nº, título e artista)":"Tracks (no., title and artist)","Número":"Number","Título":"Title",
  "Artista da faixa":"Track artist","Artista":"Artist","As alterações são gravadas nas tags dos arquivos de música.":"Changes are written to the music files' tags.",
  "Salvar":"Save","Cancelar":"Cancel","Remover álbum":"Remove album","Remover":"Remove",
  "Os arquivos vão para a lixeira e podem ser recuperados.":"The files go to the trash and can be recovered.",
  "Apagar definitivamente (não dá para desfazer)":"Delete permanently (cannot be undone)",
  "O nome do álbum não pode ficar vazio.":"The album name can't be empty.","Algumas alterações falharam:":"Some changes failed:",
  "agora":"now","há {n} min":"{n} min ago","hoje {hm}":"today {hm}","ontem {hm}":"yesterday {hm}","Não está mais na biblioteca":"No longer in the library",
  "Carregando…":"Loading…","O histórico está desligado ([history] enabled no config.toml).":"History is turned off ([history] enabled in config.toml).",
  "7 dias":"7 days","30 dias":"30 days","Sempre":"All time","reprodução":"play","reproduções":"plays","Nada tocado ainda.":"Nothing played yet.",
  "Uma música entra aqui depois de {n} s ouvindo.":"A track shows up here after {n} s of listening.","Mais tocadas":"Most played",
  "Nada neste período.":"Nothing in this period.","Artistas mais ouvidos":"Top artists","Histórico":"History",
  "Essa faixa não está mais na biblioteca":"This track is no longer in the library",
  "Nome da música":"Song title","Buscar letra":"Find lyrics","Nada tocando.":"Nothing playing.","Nada tocando":"Nothing playing","Buscando letra…":"Looking for lyrics…",
  "Não encontrei a letra desta música.":"Couldn't find lyrics for this track.","Confira o nome e tente de novo:":"Check the name and try again:",
  "Letra":"Lyrics","sincronizada (toque numa linha para pular até ela)":"synced (tap a line to jump to it)","Letra errada? Buscar outra":"Wrong lyrics? Search again",
  "Capa atualizada":"Cover updated","falha ao converter":"conversion failed","não consegui abrir a imagem":"couldn't open the image",
  "Erro ao enviar a capa: ":"Error uploading the cover: ","Buscando…":"Searching…","Nada encontrado. Tente outro termo.":"Nothing found. Try another search.",
  "Erro ao trocar a capa: ":"Error changing the cover: ","Alguns arquivos não foram removidos:":"Some files were not removed:",
  "\"{name}\" apagado":"\"{name}\" deleted","\"{name}\" movido para a lixeira":"\"{name}\" moved to the trash",
  "Toque em ▶ para começar a tocar aqui":"Tap ▶ to start playing here","Não consegui tocar: ":"Couldn't play: ",
  "Este navegador não conseguiu tocar {what}":"This browser couldn't play {what}","o arquivo":"the file",
  "Este dispositivo":"This device","Trocar onde a música toca":"Change where the music plays",
  "Tocando neste dispositivo":"Playing on this device","Tocando no {name}":"Playing on {name}",
  "Rádios":"Radio","Buscar rádio pelo nome…":"Search stations by name…","País":"Country","Todos os países":"All countries",
  "Catálogo de rádios: Radio Browser (radio-browser.info)":"Station directory: Radio Browser (radio-browser.info)",
  "Não consegui falar com o Radio Browser":"Couldn't reach Radio Browser","Favoritas":"Favorites","Ouvidas recentemente":"Recently played",
  "Resultados":"Results","Mais populares":"Most popular","Nenhuma rádio encontrada.":"No stations found.","Tirar dos favoritos":"Remove from favorites",
  "Favoritar":"Add to favorites","Adicionada aos favoritos":"Added to favorites","Removida dos favoritos":"Removed from favorites",
  "AO VIVO":"LIVE","Rádio ao vivo":"Live radio","Esta rádio não informa a música que está tocando.":"This station doesn't say which song is playing.",
  "Retrospectiva":"Recap","Período":"Period","Meses":"Months","Anos":"Years","ouvindo música":"listening to music","músicas diferentes":"different tracks",
  "artistas":"artists","dias com música":"days with music","dias seguidos (recorde)":"days in a row (record)","artistas novos":"new artists",
  "artista":"artist","dia com música":"day with music","dia seguido (recorde)":"day in a row (record)","artista novo":"new artist","música diferente":"different track",
  "{pct} de tempo ouvindo em relação a {period}":"{pct} listening time compared to {period}","Música do período":"Top track of the period",
  "{n} vezes":"{n} times","Músicas mais tocadas":"Most played tracks","Álbuns mais ouvidos":"Top albums","Quando você ouve":"When you listen",
  "Horário com mais músicas: {h}":"Busiest hour: {h}","Dia com mais músicas: {d}":"Busiest day: {d}","{n} reproduções":"{n} plays",
  "Reproduções por hora do dia":"Plays by hour of the day","Reproduções por dia da semana":"Plays by day of the week",
  "Nada tocado neste período.":"Nothing played in this period.",
  "O server.py no celular está desatualizado.":"The server.py on the phone is outdated.","Copie a versão nova e reinicie o servidor.":"Copy the new version and restart the server.",
};
const T=(s,v)=>{let r=LANG==="en"&&EN[s]||s;if(v)for(const k in v)r=r.split(`{${k}}`).join(v[k]);return r};
function i18nStatic(){                      // texts written directly in index.html
  document.documentElement.lang=LANG;
  if(LANG!=="en")return;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=T(e.textContent));
  document.querySelectorAll("[title]").forEach(e=>e.title=T(e.title));
  document.querySelectorAll("[placeholder]").forEach(e=>e.placeholder=T(e.placeholder));
  document.querySelectorAll("[aria-label]").forEach(e=>e.setAttribute("aria-label",T(e.getAttribute("aria-label"))));
}
i18nStatic();