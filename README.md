# MusicWeb

**[English](#english)** · **[Português](#português)**

---

## English

A self-hosted "Spotify" that runs on an Android phone (Termux). The phone stays connected to the receiver/speakers and plays the music with **mpv**; any device on the network controls it from the browser — or plays the music on itself.

It only needs the Python standard library. `mutagen` is optional and unlocks extra features (tags, covers, editing).

> The web interface is in Portuguese by default; set `[interface] language = "en"` in `config.toml` for English. Button names below are the Portuguese ones, with their meaning.

### Features

- **Library** by albums or artists, with search, format/quality badges (FLAC 24/96, MP3 320k…) and automatic refresh when new music is added.
- **Two audio outputs**: 📻 *Receiver* (mpv on the phone) or 📱 *Este dispositivo* ("this device", the browser). You can switch mid-song without losing your place.
- **Covers** from the album folder, the tags or the internet (iTunes / MusicBrainz / Deezer); upload or search for a different one.
- **Edit tags** (album, artist, year, tracks) and **remove albums** (they go to a trash folder).
- **Download** a whole album as a `.zip`.
- 🎤 **Lyrics**: from a `.lrc`/`.txt` file, the tags or [LRCLIB](https://lrclib.net). Synced lyrics highlight the current line and let you jump to it.
- 📻 **Internet radio**: thousands of stations from [Radio Browser](https://www.radio-browser.info), searchable by name, country and genre, with favorites; shows the song on air when the station sends it.
- 📊 **Tocadas** (played) tab: most played tracks and artists (last 7 days, 30 days or all time) and the play history.
- ✨ **Retrospectiva** (recap): a month or a year of listening — hours, top tracks, artists and albums, busiest hour and day, comparison with the previous period.
- 🎨 **Album colors**: opening an album paints the background with a gradient from its cover's dominant color.
- **Gapless playback and ReplayGain** on the Receiver (mpv).
- **Queue survives restarts**: after a reboot or crash, the queue comes back paused where it stopped — press play to continue.
- **Interface in Portuguese (BR) or English** (`[interface] language`).
- **Fast startup** on large libraries: tags are read once and cached in SQLite; later scans only read new or changed files.

### Installation (Termux)

```bash
pkg install git
git clone https://github.com/GustavoPintari/MusicWeb
cd MusicWeb
./musicweb.sh install
```

`./musicweb.sh install` installs `python` and `mpv`, installs the `requirements.txt` dependencies, asks for storage access, creates `config.toml` and sets up [start on boot](#start-with-the-phone-termuxboot). It is safe to run again to update; pass `--no-boot` to skip start on boot.

Manual setup:

```bash
pkg install python mpv
pip install -r requirements.txt   # mutagen (tags, embedded covers and lyrics)
termux-setup-storage              # gives access to ~/storage/music
```

Requires Python 3.11 or newer (for `config.toml`). The `requirements.txt` dependencies are optional: without them the server runs with fewer features.

### Usage

```bash
python server.py                       # uses the config / ~/storage/music
python server.py ~/storage/music --port 8080
python -m musicweb --config ~/my-config.toml
```

Then open `http://<phone-ip>:8080` on any device on the same network.

#### In the background: `musicweb.sh`

```bash
./musicweb.sh start      # starts in the background and restarts it if it crashes (default with no arguments)
./musicweb.sh stop       # stops it (and closes mpv)
./musicweb.sh restart
./musicweb.sh status     # running or not, config file, music folder, address and what is playing
./musicweb.sh log        # last lines of the log (log -f: follow it)
./musicweb.sh boot on    # start with the phone (boot off: don't)
```

The log is at `~/.cache/musicweb/server.log`. `start` also enables `termux-wake-lock` so Android doesn't suspend the server. Stopping or restarting keeps the saved queue: it comes back paused.

### Start with the phone (Termux:Boot)

1. Install the [Termux:Boot](https://wiki.termux.com/wiki/Termux:Boot) app from the same source as Termux (F-Droid or GitHub; builds from different sources don't work together).
2. Open Termux:Boot once so Android allows it to run at startup.
3. Run `./musicweb.sh boot on` (`install` already does it). It creates `~/.termux/boot/musicweb.sh` as a link to the project's `musicweb.sh`, which Termux:Boot runs with no arguments, i.e. `start`.

On some phones you also need to exclude Termux from battery optimization (Settings → Apps → Termux → Battery → Unrestricted) so it isn't killed.

### Configuration

Copy the example and change what you need — everything is optional:

```bash
cp config.example.toml config.toml
```

The file is looked up in this order: `--config`, the `MUSICWEB_CONFIG` variable, `./config.toml`, `~/.config/musicweb/config.toml`.

| Section / key | Default | What it does |
|---|---|---|
| `[server] host` | `0.0.0.0` | address the server listens on |
| `[server] port` | `8080` | port |
| `[server] player_name` | `Receiver` | name of the phone output shown on the page |
| `[interface] language` | `pt-BR` | interface language: `pt-BR` (Portuguese) or `en` (English) |
| `[library] music_dir` | `~/storage/music` | music folder |
| `[library] rescan_every` | `60` | seconds between checks for new music (0 disables) |
| `[library] trash_dir` | *(next to the library)* | where removed albums go |
| `[mpv] audio_output` | `opensles` | mpv audio output (`--ao`) |
| `[mpv] gapless` | `true` | no pause between tracks (the next one is preloaded) |
| `[mpv] replaygain` | `album` | volume leveling from ReplayGain tags: `album`, `track` or `no` |
| `[covers] online` | `true` | look up covers online |
| `[lyrics] online` | `true` | look up lyrics on LRCLIB |
| `[player] resume_on_start` | `false` | after a restart, play the saved queue right away |
| `[history] enabled` | `true` | record plays (history and most played) |
| `[history] min_seconds` | `30` | listening time before a track counts as played (half the track if shorter) |
| `[cache] dir` | `~/.cache/musicweb` | covers and lyrics (disposable) |
| `[data] dir` | `~/.local/share/musicweb` | `musicweb.db`: scan cache, play history and saved queue |

**Priority:** defaults < `config.toml` < environment variables < command line.
The older variables still work: `MPV_AO`, `COVERS_ONLINE`, `LYRICS_ONLINE`, `RESCAN_EVERY`, `PLAYER_NAME`, `TRASH`, `MUSIC_DIR`; plus `MUSICWEB_LANGUAGE`.

### Organizing your music

The server reads the tags when `mutagen` is installed; without it, it uses the folders:

```
music/
└── Artist/
    └── Album/
        ├── 01 Track.flac
        ├── 01 Track.lrc        ← lyrics (optional)
        ├── cover.jpg           ← cover (optional)
        └── CD2/…               ← extra discs
```

### Lyrics

When you tap **🎤 Letra** (lyrics), the server looks, in this order, for:

1. a `.lrc` or `.txt` file with the same name as the track;
2. lyrics stored in the tags (ID3 `USLT`, `LYRICS`, `©lyr`);
3. LRCLIB, by artist, track name, album and duration.

If the lyrics are wrong (or missing), use **"Buscar outra"** (search again) to fix the artist/title. Lyrics that are found are cached.

### Internet radio

The 📻 button opens the station list, from [Radio Browser](https://www.radio-browser.info) — a free, community-run directory (no account or API key). Search by name, pick a country (all countries the first time; the last choice is remembered) and a genre, and star your favorites. The server picks a Radio Browser mirror, sends a descriptive User-Agent and reports a "click" when a station is played, as the project asks.

On the Receiver, mpv plays the stream and shows the song on air (ICY metadata), which is also used to look up the lyrics. In the browser, MP3/AAC streams play directly and HLS (`.m3u8`) streams play natively or through [hls.js](https://github.com/video-dev/hls.js) (loaded only when needed). Stations that publish a playlist (`.pls`/`.m3u`) have it read again each time they are played, because some hand out links that expire after a few days. Radio is not counted in the history or the recap.

### Database

`musicweb.db` (SQLite, in `[data] dir`) stores:

- **scan cache** — the tags of each file, with its modification time and size; only new or changed files are read again;
- **play history** — one row per play; a track counts after `min_seconds` of actual listening (seeking doesn't count), on mpv and in the browser;
- **saved queue** — the queue, the current track and position (saved every ~10 s while playing and on pause);
- **radio** — favorite and recent stations and the last search filters.

SQLite comes with Python, so there is nothing extra to install. To back up your history, copy `musicweb.db`; deleting it only resets the history and the queue (the scan cache is rebuilt on the next start).

### Project structure

```
server.py               shortcut: python server.py
config.example.toml     configuration template
requirements.txt        Python dependencies (mutagen)
musicweb.sh             Termux control: start, stop, restart, status, log, install, boot on/off
musicweb/
├── app.py              startup (arguments, configuration, threads)
├── info.py             `musicweb.sh status` details
├── config.py           reads config.toml / environment
├── state.py            shared state (library, radio stations, queue)
├── db.py               SQLite: schema, scan cache, key/value storage
├── history.py          play history and most played
├── library.py          folder scan (with cache), album grouping, automatic refresh
├── covers.py           local, embedded and online covers; cover changes
├── player.py           mpv control (queue, events, status, saved queue, play counting)
├── editor.py           tag editing and album removal
├── radio.py            internet radio (Radio Browser): search, favorites, recent
├── retro.py            retrospective (recap) of a month or a year
├── lyrics.py           lyrics (.lrc, tags, LRCLIB)
├── web.py              HTTP server: API routes, streaming and downloads
├── i18n.py             interface language for server messages (the page has its own dictionary)
├── util.py             small shared helpers
└── static/            the page, served as is (no build step)
    ├── index.html      the HTML; loads the CSS and the scripts below in order
    ├── app.css         styles
    └── js/             plain scripts sharing one global scope, loaded in this order:
        ├── util.js       shared helpers and state
        ├── i18n.js       Portuguese → English dictionary
        ├── colors.js     album colors and the album page background (glass / vinyl)
        ├── library.js    album grid, artists, album page, tag editing, covers
        ├── radio.js      internet radio
        ├── plays.js      most played and history
        ├── retro.js      retrospective
        ├── lyrics.js     lyrics
        ├── player.js     player bar and the two outputs (Receiver / this device)
        └── main.js       events and startup
```

Module dependencies (no cycles): `config` → `state`/`util`/`db` → `history`/`radio` → `covers` → `library` / `player` / `lyrics` / `retro` → `editor` → `web` → `app`.

### API

| Method | Route | Description |
|---|---|---|
| GET | `/static/<file>` | the page's CSS and JS (the page links them with `?v=` + modification time, so updates are never stale) |
| GET | `/api/library` | albums and tracks |
| GET | `/api/status` | what mpv is playing |
| GET | `/api/stream/<id>` | track audio (supports Range; `?dl` to download) |
| GET | `/api/download/<album>` | album as `.zip` |
| GET | `/api/cover/<album>` | cover |
| GET | `/api/cover_search?q=` | cover suggestions |
| GET | `/api/lyrics?id=[&artist=&title=]` | lyrics |
| GET | `/api/stats?days=` | most played tracks/artists and history (`days=0`: all time) |
| GET | `/api/retro` · `/api/retro?period=2026-10` | periods with plays · recap of a month (`YYYY-MM`) or year (`YYYY`) |
| GET | `/api/radio` · `/api/radio/countries` · `/api/radio/tags` · `/api/radio/search?q=&country=&tag=` | radio: favorites/recent/filters, countries, genres, search |
| POST | `/api/play` `{album}`, `{id, t}`, `{playlist, pos}` or `{queue: [ids], pos}` | play on mpv |
| POST | `/api/pause`, `/resume`, `/stop`, `/next`, `/prev` | controls |
| POST | `/api/seek` `{t}` · `/api/volume` `{v}` or `{delta}` | position and volume |
| POST | `/api/rescan` | re-reads the library |
| POST | `/api/edit` · `/api/delete` | edit tags · remove album |
| POST | `/api/cover_set` `{album, url}` · `/api/cover_upload?album=` | change cover |
| POST | `/api/played` `{id}` | the browser reports a play ("this device" output) |
| POST | `/api/radio/select` `{uuid}` · `/api/radio/favorite` `{uuid, on}` | prepare a station to play · (un)favorite it |

### License

[MIT](LICENSE)

---

## Português

Um "Spotify" auto-hospedado para rodar no celular (Termux). O celular fica ligado ao receiver/caixa de som e toca as músicas com o **mpv**; qualquer aparelho da rede controla tudo pelo navegador — ou toca a música nele mesmo.

Só usa a biblioteca padrão do Python. O `mutagen` é opcional e libera recursos extras (tags, capas, edição).

### Recursos

- **Biblioteca** por álbuns ou artistas, com busca, formato/qualidade (FLAC 24/96, MP3 320k…) e atualização automática quando entram músicas novas.
- **Duas saídas de áudio**: 📻 *Receiver* (o mpv no celular) ou 📱 *Este dispositivo* (o navegador). Dá para trocar no meio da música sem perder o ponto.
- **Capas** da pasta do álbum, das tags ou da internet (iTunes / MusicBrainz / Deezer); dá para enviar ou buscar outra capa.
- **Editar tags** (álbum, artista, ano, faixas) e **remover álbuns** (vão para uma lixeira).
- **Baixar** o álbum inteiro em `.zip`.
- 🎤 **Letras**: de arquivo `.lrc`/`.txt`, das tags ou do [LRCLIB](https://lrclib.net). Letras sincronizadas destacam a linha atual e permitem pular para ela.
- 📻 **Rádios online**: milhares de rádios do [Radio Browser](https://www.radio-browser.info), com busca por nome, país e gênero e favoritas; mostra a música no ar quando a rádio informa.
- 📊 Aba **Tocadas**: músicas e artistas mais ouvidos (últimos 7 dias, 30 dias ou sempre) e o histórico de reprodução.
- ✨ **Retrospectiva**: um mês ou um ano de música — horas, músicas, artistas e álbuns mais ouvidos, horário e dia preferidos, comparação com o período anterior.
- 🎨 **Cores do disco**: ao abrir um álbum, o fundo ganha um degradê com a cor dominante da capa.
- **Reprodução sem pausa entre faixas (gapless) e ReplayGain** no Receiver (mpv).
- **Fila que sobrevive a reinício**: depois de religar o celular ou de uma queda, a fila volta pausada onde parou — é só apertar play.
- **Interface em português (BR) ou inglês** (`[interface] language`).
- **Inicialização rápida** em bibliotecas grandes: as tags são lidas uma vez e guardadas no SQLite; as varreduras seguintes só leem arquivos novos ou alterados.

### Instalação (Termux)

```bash
pkg install git
git clone https://github.com/GustavoPintari/MusicWeb
cd MusicWeb
./musicweb.sh install
```

O `./musicweb.sh install` instala o `python` e o `mpv`, instala as dependências do `requirements.txt`, pede acesso ao armazenamento, cria o `config.toml` e configura o [início automático](#iniciar-junto-com-o-celular-termuxboot). Pode rodar de novo para atualizar; use `--no-boot` se não quiser o início automático.

Para fazer à mão:

```bash
pkg install python mpv
pip install -r requirements.txt   # mutagen (tags, capas e letras embutidas)
termux-setup-storage              # dá acesso a ~/storage/music
```

Requer Python 3.11 ou mais novo, por causa do `config.toml`. As dependências do `requirements.txt` são opcionais: sem elas, o servidor roda com menos recursos.

### Uso

```bash
python server.py                       # usa a configuração / ~/storage/music
python server.py ~/storage/music --port 8080
python -m musicweb --config ~/meu-config.toml
```

Depois abra `http://<ip-do-celular>:8080` em qualquer aparelho da mesma rede.

#### Em segundo plano: `musicweb.sh`

```bash
./musicweb.sh start      # inicia em segundo plano e reinicia sozinho se cair (padrão sem argumentos)
./musicweb.sh stop       # para (e encerra o mpv)
./musicweb.sh restart
./musicweb.sh status     # se está rodando, arquivo de config, pasta de músicas, endereço e o que está tocando
./musicweb.sh log        # últimas linhas do log (log -f: acompanha)
./musicweb.sh boot on    # inicia junto com o celular (boot off: não inicia)
```

O log fica em `~/.cache/musicweb/server.log`. O `start` também ativa o `termux-wake-lock` para o Android não suspender o servidor. Parar ou reiniciar mantém a fila salva: ela volta pausada.

### Iniciar junto com o celular (Termux:Boot)

1. Instale o app [Termux:Boot](https://wiki.termux.com/wiki/Termux:Boot) da mesma loja em que instalou o Termux (F-Droid ou GitHub; versões de lojas diferentes não conversam entre si).
2. Abra o Termux:Boot uma vez, para o Android liberar a execução na inicialização.
3. Rode `./musicweb.sh boot on` (o `install` já faz isso). Ele cria `~/.termux/boot/musicweb.sh` como um link para o `musicweb.sh` do projeto, que o Termux:Boot executa sem argumentos, ou seja, `start`.

Em alguns aparelhos também é preciso tirar o Termux da otimização de bateria (Configurações → Apps → Termux → Bateria → Sem restrições) para ele não ser encerrado.

### Configuração

Copie o exemplo e ajuste o que quiser — tudo é opcional:

```bash
cp config.example.toml config.toml
```

O arquivo é procurado nesta ordem: `--config`, variável `MUSICWEB_CONFIG`, `./config.toml`, `~/.config/musicweb/config.toml`.

| Seção / chave | Padrão | O que faz |
|---|---|---|
| `[server] host` | `0.0.0.0` | endereço em que o servidor escuta |
| `[server] port` | `8080` | porta |
| `[server] player_name` | `Receiver` | nome da saída do celular na página |
| `[interface] language` | `pt-BR` | idioma da interface: `pt-BR` (português) ou `en` (inglês) |
| `[library] music_dir` | `~/storage/music` | pasta das músicas |
| `[library] rescan_every` | `60` | segundos entre buscas por músicas novas (0 desliga) |
| `[library] trash_dir` | *(ao lado da biblioteca)* | para onde vão os álbuns removidos |
| `[mpv] audio_output` | `opensles` | saída de áudio do mpv (`--ao`) |
| `[mpv] gapless` | `true` | sem pausa entre as faixas (a próxima é pré-carregada) |
| `[mpv] replaygain` | `album` | equaliza o volume pelas tags ReplayGain: `album`, `track` ou `no` |
| `[covers] online` | `true` | busca capas na internet |
| `[lyrics] online` | `true` | busca letras no LRCLIB |
| `[player] resume_on_start` | `false` | depois de reiniciar, já toca a fila salva |
| `[history] enabled` | `true` | registra as reproduções (histórico e mais tocadas) |
| `[history] min_seconds` | `30` | tempo ouvindo até a música contar como tocada (metade da faixa, se for mais curta) |
| `[cache] dir` | `~/.cache/musicweb` | capas e letras (descartável) |
| `[data] dir` | `~/.local/share/musicweb` | `musicweb.db`: cache da varredura, histórico e fila salva |

**Prioridade:** padrão < `config.toml` < variáveis de ambiente < linha de comando.
As variáveis antigas continuam valendo: `MPV_AO`, `COVERS_ONLINE`, `LYRICS_ONLINE`, `RESCAN_EVERY`, `PLAYER_NAME`, `TRASH`, `MUSIC_DIR`; e também `MUSICWEB_LANGUAGE`.

### Organização das músicas

O servidor lê as tags quando o `mutagen` está instalado; sem ele, usa as pastas:

```
music/
└── Artista/
    └── Álbum/
        ├── 01 Faixa.flac
        ├── 01 Faixa.lrc        ← letra (opcional)
        ├── cover.jpg           ← capa (opcional)
        └── CD2/…               ← discos extras
```

### Letras

Ao tocar no botão **🎤 Letra**, o servidor procura, nesta ordem:

1. arquivo `.lrc` ou `.txt` com o mesmo nome da música;
2. letra gravada nas tags (ID3 `USLT`, `LYRICS`, `©lyr`);
3. LRCLIB, pelo artista, nome da faixa, álbum e duração.

Se vier a letra errada (ou nenhuma), use **"Buscar outra"** para corrigir artista/música. As letras encontradas ficam no cache.

### Rádios online

O botão 📻 abre a lista de rádios, vinda do [Radio Browser](https://www.radio-browser.info) — um catálogo gratuito e comunitário (sem conta nem chave de API). Busque pelo nome, escolha o país (na primeira vez, todos os países; depois vale a última escolha) e o gênero, e marque as favoritas com ★. O servidor escolhe um espelho do Radio Browser, se identifica com um User-Agent e registra o "clique" ao tocar uma rádio, como o projeto pede.

No Receiver, o mpv toca o stream e mostra a música no ar (metadados ICY), que também é usada para buscar a letra. No navegador, streams MP3/AAC tocam direto e streams HLS (`.m3u8`) tocam de forma nativa ou pelo [hls.js](https://github.com/video-dev/hls.js) (carregado só quando precisa). Rádios que publicam uma playlist (`.pls`/`.m3u`) têm a playlist lida de novo a cada vez que tocam, porque algumas entregam links que expiram em poucos dias. Rádio não entra no histórico nem na retrospectiva.

### Banco de dados

O `musicweb.db` (SQLite, em `[data] dir`) guarda:

- **cache da varredura** — as tags de cada arquivo, com data de modificação e tamanho; só arquivos novos ou alterados são lidos de novo;
- **histórico** — uma linha por reprodução; a música conta depois de `min_seconds` ouvindo de verdade (pular trechos não conta), tanto no mpv quanto no navegador;
- **fila salva** — a fila, a faixa atual e a posição (salva a cada ~10 s tocando e ao pausar);
- **rádios** — favoritas, recentes e os últimos filtros de busca.

O SQLite já vem com o Python, então não há nada extra para instalar. Para fazer backup do histórico, copie o `musicweb.db`; apagá-lo só zera o histórico e a fila (o cache da varredura é refeito na próxima inicialização).

### Estrutura do projeto

```
server.py               atalho: python server.py
config.example.toml     modelo de configuração
requirements.txt        dependências Python (mutagen)
musicweb.sh             controle no Termux: start, stop, restart, status, log, install, boot on/off
musicweb/
├── app.py              inicialização (argumentos, configuração, threads)
├── info.py             detalhes do `musicweb.sh status`
├── config.py           leitura do config.toml / ambiente
├── state.py            estado compartilhado (biblioteca, rádios, fila)
├── db.py               SQLite: esquema, cache da varredura, chave/valor
├── history.py          histórico e mais tocadas
├── library.py          varredura da pasta (com cache), agrupamento em álbuns, atualização automática
├── covers.py           capas locais, embutidas e online; troca de capa
├── player.py           controle do mpv (fila, eventos, status, fila salva, contagem de reproduções)
├── editor.py           edição de tags e remoção de álbuns
├── radio.py            rádios online (Radio Browser): busca, favoritas, recentes
├── retro.py            retrospectiva de um mês ou de um ano
├── lyrics.py           letras (.lrc, tags, LRCLIB)
├── web.py              servidor HTTP: rotas da API, streaming e downloads
├── i18n.py             idioma da interface nas mensagens do servidor (a página tem o próprio dicionário)
├── util.py             funções pequenas compartilhadas
└── static/            a página, servida como está (sem etapa de build)
    ├── index.html      o HTML; carrega o CSS e os scripts abaixo, em ordem
    ├── app.css         estilos
    └── js/             scripts comuns que dividem o mesmo escopo global, carregados nesta ordem:
        ├── util.js       funções e estado compartilhados
        ├── i18n.js       dicionário português → inglês
        ├── colors.js     cores do álbum e fundo da página do álbum (vidro / vinil)
        ├── library.js    grade de álbuns, artistas, página do álbum, edição de tags, capas
        ├── radio.js      rádios online
        ├── plays.js      mais tocadas e histórico
        ├── retro.js      retrospectiva
        ├── lyrics.js     letras
        ├── player.js     barra do player e as duas saídas (Receiver / este dispositivo)
        └── main.js       eventos e inicialização
```

Dependências entre módulos (sem ciclos): `config` → `state`/`util`/`db` → `history`/`radio` → `covers` → `library` / `player` / `lyrics` / `retro` → `editor` → `web` → `app`.

### API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/static/<arquivo>` | CSS e JS da página (a página usa `?v=` + data de modificação, então uma atualização nunca fica velha no navegador) |
| GET | `/api/library` | álbuns e faixas |
| GET | `/api/status` | o que o mpv está tocando |
| GET | `/api/stream/<id>` | áudio da faixa (com Range; `?dl` para baixar) |
| GET | `/api/download/<álbum>` | álbum em `.zip` |
| GET | `/api/cover/<álbum>` | capa |
| GET | `/api/cover_search?q=` | sugestões de capa |
| GET | `/api/lyrics?id=[&artist=&title=]` | letra |
| GET | `/api/stats?days=` | mais tocadas, artistas e histórico (`days=0`: sempre) |
| GET | `/api/retro` · `/api/retro?period=2026-10` | períodos com músicas · retrospectiva de um mês (`AAAA-MM`) ou ano (`AAAA`) |
| GET | `/api/radio` · `/api/radio/countries` · `/api/radio/tags` · `/api/radio/search?q=&country=&tag=` | rádios: favoritas/recentes/filtros, países, gêneros, busca |
| POST | `/api/play` `{album}`, `{id, t}`, `{playlist, pos}` ou `{queue: [ids], pos}` | toca no mpv |
| POST | `/api/pause`, `/resume`, `/stop`, `/next`, `/prev` | controles |
| POST | `/api/seek` `{t}` · `/api/volume` `{v}` ou `{delta}` | posição e volume |
| POST | `/api/rescan` | relê a biblioteca |
| POST | `/api/edit` · `/api/delete` | editar tags · remover álbum |
| POST | `/api/cover_set` `{album, url}` · `/api/cover_upload?album=` | trocar capa |
| POST | `/api/played` `{id}` | o navegador avisa uma reprodução (saída "Este dispositivo") |
| POST | `/api/radio/select` `{uuid}` · `/api/radio/favorite` `{uuid, on}` | prepara uma rádio para tocar · favorita/desfavorita |

### Licença

[MIT](LICENSE)
