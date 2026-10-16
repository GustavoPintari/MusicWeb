# MusicWeb

**[English](#english)** · **[Português](#português)**

---

## English

A self-hosted "Spotify" that runs on an Android phone (Termux). The phone stays connected to the receiver/speakers and plays the music with **mpv**; any device on the network controls it from the browser — or plays the music on itself.

It only needs the Python standard library. `mutagen` and `yt-dlp` are optional and unlock extra features.

> The web interface is in Portuguese by default; set `[interface] language = "en"` in `config.toml` for English. Button names below are the Portuguese ones, with their meaning.

### Features

- **Library** by albums or artists, with search, format/quality badges (FLAC 24/96, MP3 320k…) and automatic refresh when new music is added.
- **Two audio outputs**: 📻 *Receiver* (mpv on the phone) or 📱 *Este dispositivo* ("this device", the browser). You can switch mid-song without losing your place.
- **Covers** from the album folder, the tags or the internet (iTunes / MusicBrainz / Deezer); upload or search for a different one.
- **Edit tags** (album, artist, year, tracks) and **remove albums** (they go to a trash folder).
- **Download** a whole album as a `.zip`.
- 🎤 **Lyrics**: from a `.lrc`/`.txt` file, the tags or [LRCLIB](https://lrclib.net). Synced lyrics highlight the current line and let you jump to it.
- ▶ **YouTube**: paste a video or **playlist** link and play only the audio, on either output.
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
pip install -r requirements.txt   # mutagen (tags, embedded covers and lyrics) and yt-dlp (YouTube)
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
| `[youtube] cookies` | *(empty)* | `cookies.txt` in case YouTube asks you to sign in |
| `[youtube] max_history` | `50` | videos kept in "Tocados recentemente" (recently played) |
| `[youtube] format` | m4a / best audio | format requested from yt-dlp |
| `[youtube] playlist_max` | `200` | videos read from a playlist link |
| `[youtube] pot_server` | `~/bgutil-ytdlp-pot-provider/server` | PO token server started with MusicWeb (`""` = don't start) |
| `[youtube] pot_url` | `http://127.0.0.1:4416` | where the PO token server answers |
| `[player] resume_on_start` | `false` | after a restart, play the saved queue right away |
| `[history] enabled` | `true` | record plays (history and most played) |
| `[history] min_seconds` | `30` | listening time before a track counts as played (half the track if shorter) |
| `[cache] dir` | `~/.cache/musicweb` | covers, lyrics and YouTube history (disposable) |
| `[data] dir` | `~/.local/share/musicweb` | `musicweb.db`: scan cache, play history and saved queue |

**Priority:** defaults < `config.toml` < environment variables < command line.
The older variables still work: `MPV_AO`, `COVERS_ONLINE`, `LYRICS_ONLINE`, `RESCAN_EVERY`, `PLAYER_NAME`, `YT_COOKIES`, `TRASH`, `MUSIC_DIR`; plus `MUSICWEB_LANGUAGE`.

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

### YouTube

Requires `yt-dlp`. The audio goes through the server itself (`/api/stream/yt_<id>`), which renews the YouTube link when it expires — so it works both in mpv and in the browser.

**Playlists**: a link with `list=` (a playlist, an album on YouTube Music or a mix) is read in one go with `yt-dlp --flat-playlist`, without downloading anything; each video is only resolved when its turn comes. Private or deleted videos are skipped. The playlist shows up as a single entry in "recently played".

If you see *"o YouTube pediu login para confirmar que não é um robô"* (YouTube asked to sign in to confirm you're not a bot):

1. update yt-dlp: `pip install -U yt-dlp`;
2. install the PO token provider (below), which usually solves it without signing in;
3. if it keeps happening, export your YouTube cookies ([how to](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)) and set `[youtube] cookies = "~/cookies.txt"`.

The check depends mostly on the IP address: it is rare on home Wi-Fi or mobile data and common behind VPNs and cloud servers.

**PO token (no cookies)**: [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) makes the "proof of origin" token YouTube asks for. It has a yt-dlp plugin and a small Node.js server. To install both (Node.js 22 or newer; on Termux the script installs it, plus what's needed to compile the `canvas` module):

```sh
./pot-setup.sh
./musicweb.sh restart
```

MusicWeb starts the server together with itself (only on `127.0.0.1`, since it has no authentication), restarts it if it stops and stops it on exit; the startup log shows `PO token=sim`. If something already answers on `[youtube] pot_url` (for example the project's Docker image), that one is used. Run `./pot-setup.sh` again to update the plugin and the server together (they must be the same version). When Node.js is installed and Deno isn't, yt-dlp is also told to use Node.js as its JavaScript runtime (`--js-runtimes node`). A token helps but doesn't guarantee anything: if the IP itself is blocked, only cookies (or another network) help.

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
requirements.txt        Python dependencies (mutagen, yt-dlp)
musicweb.sh             Termux control: start, stop, restart, status, log, install, boot on/off
pot-setup.sh            installs/updates the YouTube PO token provider (plugin + Node.js server)
musicweb/
├── app.py              startup (arguments, configuration, threads)
├── info.py             `musicweb.sh status` details
├── config.py           reads config.toml / environment
├── state.py            shared state (library, queue, YouTube history)
├── db.py               SQLite: schema, scan cache, key/value storage
├── history.py          play history and most played
├── library.py          folder scan (with cache), album grouping, automatic refresh
├── covers.py           local, embedded and online covers; cover changes
├── player.py           mpv control (queue, events, status, saved queue, play counting)
├── editor.py           tag editing and album removal
├── youtube.py          yt-dlp, direct links, playlists and history
├── pot.py              YouTube PO token server (bgutil-ytdlp-pot-provider): start, restart, stop
├── radio.py            internet radio (Radio Browser): search, favorites, recent
├── retro.py            retrospective (recap) of a month or a year
├── lyrics.py           lyrics (.lrc, tags, LRCLIB)
├── web.py              HTTP server: API routes, streaming and downloads
├── i18n.py             interface language for server messages (the page has its own dictionary)
├── util.py             small shared helpers
└── static/index.html   the page (HTML, CSS and JS in one file)
```

Module dependencies (no cycles): `config` → `state`/`util`/`db`/`pot` → `youtube`/`history`/`radio` → `covers` → `library` / `player` / `lyrics` / `retro` → `editor` → `web` → `app`.

### API

| Method | Route | Description |
|---|---|---|
| GET | `/api/library` | albums, tracks and YouTube history |
| GET | `/api/status` | what mpv is playing |
| GET | `/api/stream/<id>` | track audio (supports Range; `?dl` to download) |
| GET | `/api/download/<album>` | album as `.zip` |
| GET | `/api/cover/<album>` | cover |
| GET | `/api/cover_search?q=` | cover suggestions |
| GET | `/api/lyrics?id=[&artist=&title=]` | lyrics |
| GET | `/api/stats?days=` | most played tracks/artists and history (`days=0`: all time) |
| GET | `/api/retro` · `/api/retro?period=2026-10` | periods with plays · recap of a month (`YYYY-MM`) or year (`YYYY`) |
| GET | `/api/yt_playlist?id=` | videos of a YouTube playlist |
| GET | `/api/radio` · `/api/radio/countries` · `/api/radio/tags` · `/api/radio/search?q=&country=&tag=` | radio: favorites/recent/filters, countries, genres, search |
| POST | `/api/play` `{album}`, `{id, t}`, `{playlist, pos}` or `{queue: [ids], pos}` | play on mpv |
| POST | `/api/pause`, `/resume`, `/stop`, `/next`, `/prev` | controls |
| POST | `/api/seek` `{t}` · `/api/volume` `{v}` or `{delta}` | position and volume |
| POST | `/api/rescan` | re-reads the library |
| POST | `/api/edit` · `/api/delete` | edit tags · remove album |
| POST | `/api/cover_set` `{album, url}` · `/api/cover_upload?album=` | change cover |
| POST | `/api/yt` `{url}` · `/api/yt_remove` `{id}` | YouTube |
| POST | `/api/played` `{id}` | the browser reports a play ("this device" output) |
| POST | `/api/radio/select` `{uuid}` · `/api/radio/favorite` `{uuid, on}` | prepare a station to play · (un)favorite it |

### License

[MIT](LICENSE)

---

## Português

Um "Spotify" auto-hospedado para rodar no celular (Termux). O celular fica ligado ao receiver/caixa de som e toca as músicas com o **mpv**; qualquer aparelho da rede controla tudo pelo navegador — ou toca a música nele mesmo.

Só usa a biblioteca padrão do Python. `mutagen` e `yt-dlp` são opcionais e liberam recursos extras.

### Recursos

- **Biblioteca** por álbuns ou artistas, com busca, formato/qualidade (FLAC 24/96, MP3 320k…) e atualização automática quando entram músicas novas.
- **Duas saídas de áudio**: 📻 *Receiver* (o mpv no celular) ou 📱 *Este dispositivo* (o navegador). Dá para trocar no meio da música sem perder o ponto.
- **Capas** da pasta do álbum, das tags ou da internet (iTunes / MusicBrainz / Deezer); dá para enviar ou buscar outra capa.
- **Editar tags** (álbum, artista, ano, faixas) e **remover álbuns** (vão para uma lixeira).
- **Baixar** o álbum inteiro em `.zip`.
- 🎤 **Letras**: de arquivo `.lrc`/`.txt`, das tags ou do [LRCLIB](https://lrclib.net). Letras sincronizadas destacam a linha atual e permitem pular para ela.
- ▶ **YouTube**: cole o link de um vídeo ou de uma **playlist** e toque só o áudio, em qualquer uma das saídas.
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
pip install -r requirements.txt   # mutagen (tags, capas e letras embutidas) e yt-dlp (YouTube)
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
| `[youtube] cookies` | *(vazio)* | `cookies.txt` caso o YouTube peça login |
| `[youtube] max_history` | `50` | vídeos guardados em "Tocados recentemente" |
| `[youtube] format` | m4a / melhor áudio | formato pedido ao yt-dlp |
| `[youtube] playlist_max` | `200` | vídeos lidos de um link de playlist |
| `[youtube] pot_server` | `~/bgutil-ytdlp-pot-provider/server` | servidor de PO token iniciado com o MusicWeb (`""` = não iniciar) |
| `[youtube] pot_url` | `http://127.0.0.1:4416` | onde o servidor de PO token responde |
| `[player] resume_on_start` | `false` | depois de reiniciar, já toca a fila salva |
| `[history] enabled` | `true` | registra as reproduções (histórico e mais tocadas) |
| `[history] min_seconds` | `30` | tempo ouvindo até a música contar como tocada (metade da faixa, se for mais curta) |
| `[cache] dir` | `~/.cache/musicweb` | capas, letras e histórico do YouTube (descartável) |
| `[data] dir` | `~/.local/share/musicweb` | `musicweb.db`: cache da varredura, histórico e fila salva |

**Prioridade:** padrão < `config.toml` < variáveis de ambiente < linha de comando.
As variáveis antigas continuam valendo: `MPV_AO`, `COVERS_ONLINE`, `LYRICS_ONLINE`, `RESCAN_EVERY`, `PLAYER_NAME`, `YT_COOKIES`, `TRASH`, `MUSIC_DIR`; e também `MUSICWEB_LANGUAGE`.

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

### YouTube

Precisa do `yt-dlp`. O áudio passa pelo próprio servidor (`/api/stream/yt_<id>`), que renova o link do YouTube quando ele expira — assim funciona tanto no mpv quanto no navegador.

**Playlists**: um link com `list=` (playlist, álbum do YouTube Music ou mix) é lido de uma vez com `yt-dlp --flat-playlist`, sem baixar nada; cada vídeo só é resolvido quando chega a vez dele. Vídeos privados ou apagados são pulados. A playlist aparece como um item só em "Tocados recentemente".

Se aparecer *"o YouTube pediu login para confirmar que não é um robô"*:

1. atualize o yt-dlp: `pip install -U yt-dlp`;
2. instale o gerador de PO token (abaixo), que costuma resolver sem login;
3. se continuar, exporte os cookies do YouTube ([como fazer](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)) e configure `[youtube] cookies = "~/cookies.txt"`.

O bloqueio depende principalmente do IP: é raro na Wi-Fi de casa ou nos dados móveis e comum atrás de VPN e servidores na nuvem.

**PO token (sem cookies)**: o [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) gera o token de "prova de origem" que o YouTube pede. Ele tem um plugin do yt-dlp e um pequeno servidor em Node.js. Para instalar os dois (Node.js 22 ou mais novo; no Termux o script instala, junto com o necessário para compilar o módulo `canvas`):

```sh
./pot-setup.sh
./musicweb.sh restart
```

O MusicWeb inicia o servidor junto com ele (só em `127.0.0.1`, porque o servidor não tem autenticação), reinicia se ele parar e encerra ao sair; o log de inicialização mostra `PO token=sim`. Se algo já responder em `[youtube] pot_url` (por exemplo a imagem Docker do projeto), esse é usado. Rode `./pot-setup.sh` de novo para atualizar plugin e servidor juntos (precisam ser da mesma versão). Com o Node.js instalado e sem o Deno, o yt-dlp também passa a usar o Node.js como JavaScript runtime (`--js-runtimes node`). O token ajuda, mas não garante: se o próprio IP estiver bloqueado, só os cookies (ou outra rede) resolvem.

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
requirements.txt        dependências Python (mutagen, yt-dlp)
musicweb.sh             controle no Termux: start, stop, restart, status, log, install, boot on/off
pot-setup.sh            instala/atualiza o gerador de PO token do YouTube (plugin + servidor Node.js)
musicweb/
├── app.py              inicialização (argumentos, configuração, threads)
├── info.py             detalhes do `musicweb.sh status`
├── config.py           leitura do config.toml / ambiente
├── state.py            estado compartilhado (biblioteca, fila, histórico do YouTube)
├── db.py               SQLite: esquema, cache da varredura, chave/valor
├── history.py          histórico e mais tocadas
├── library.py          varredura da pasta (com cache), agrupamento em álbuns, atualização automática
├── covers.py           capas locais, embutidas e online; troca de capa
├── player.py           controle do mpv (fila, eventos, status, fila salva, contagem de reproduções)
├── editor.py           edição de tags e remoção de álbuns
├── youtube.py          yt-dlp, links diretos, playlists e histórico
├── pot.py              servidor de PO token do YouTube (bgutil-ytdlp-pot-provider): inicia, reinicia, encerra
├── radio.py            rádios online (Radio Browser): busca, favoritas, recentes
├── retro.py            retrospectiva de um mês ou de um ano
├── lyrics.py           letras (.lrc, tags, LRCLIB)
├── web.py              servidor HTTP: rotas da API, streaming e downloads
├── i18n.py             idioma da interface nas mensagens do servidor (a página tem o próprio dicionário)
├── util.py             funções pequenas compartilhadas
└── static/index.html   a página (HTML, CSS e JS num arquivo só)
```

Dependências entre módulos (sem ciclos): `config` → `state`/`util`/`db`/`pot` → `youtube`/`history`/`radio` → `covers` → `library` / `player` / `lyrics` / `retro` → `editor` → `web` → `app`.

### API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/library` | álbuns, faixas e histórico do YouTube |
| GET | `/api/status` | o que o mpv está tocando |
| GET | `/api/stream/<id>` | áudio da faixa (com Range; `?dl` para baixar) |
| GET | `/api/download/<álbum>` | álbum em `.zip` |
| GET | `/api/cover/<álbum>` | capa |
| GET | `/api/cover_search?q=` | sugestões de capa |
| GET | `/api/lyrics?id=[&artist=&title=]` | letra |
| GET | `/api/stats?days=` | mais tocadas, artistas e histórico (`days=0`: sempre) |
| GET | `/api/retro` · `/api/retro?period=2026-10` | períodos com músicas · retrospectiva de um mês (`AAAA-MM`) ou ano (`AAAA`) |
| GET | `/api/yt_playlist?id=` | vídeos de uma playlist do YouTube |
| GET | `/api/radio` · `/api/radio/countries` · `/api/radio/tags` · `/api/radio/search?q=&country=&tag=` | rádios: favoritas/recentes/filtros, países, gêneros, busca |
| POST | `/api/play` `{album}`, `{id, t}`, `{playlist, pos}` ou `{queue: [ids], pos}` | toca no mpv |
| POST | `/api/pause`, `/resume`, `/stop`, `/next`, `/prev` | controles |
| POST | `/api/seek` `{t}` · `/api/volume` `{v}` ou `{delta}` | posição e volume |
| POST | `/api/rescan` | relê a biblioteca |
| POST | `/api/edit` · `/api/delete` | editar tags · remover álbum |
| POST | `/api/cover_set` `{album, url}` · `/api/cover_upload?album=` | trocar capa |
| POST | `/api/yt` `{url}` · `/api/yt_remove` `{id}` | YouTube |
| POST | `/api/played` `{id}` | o navegador avisa uma reprodução (saída "Este dispositivo") |
| POST | `/api/radio/select` `{uuid}` · `/api/radio/favorite` `{uuid, on}` | prepara uma rádio para tocar · favorita/desfavorita |

### Licença

[MIT](LICENSE)
