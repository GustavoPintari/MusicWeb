# MusicWeb

Um "Spotify" auto-hospedado para rodar no celular (Termux). O celular fica ligado ao receiver/caixa de som e toca as músicas com o **mpv**; qualquer aparelho da rede controla tudo pelo navegador — ou toca a música nele mesmo.

Só usa a biblioteca padrão do Python. `mutagen` e `yt-dlp` são opcionais e liberam recursos extras.

## Recursos

- **Biblioteca** por álbuns ou artistas, com busca, formato/qualidade (FLAC 24/96, MP3 320k…) e atualização automática quando entram músicas novas.
- **Duas saídas de áudio**: 📻 *Receiver* (o mpv no celular) ou 📱 *Este dispositivo* (o navegador). Dá para trocar no meio da música sem perder o ponto.
- **Capas** da pasta do álbum, das tags ou da internet (iTunes / MusicBrainz / Deezer); dá para enviar ou buscar outra capa.
- **Editar tags** (álbum, artista, ano, faixas) e **remover álbuns** (vão para uma lixeira).
- **Baixar** o álbum inteiro em `.zip`.
- 🎤 **Letras**: de arquivo `.lrc`/`.txt`, das tags ou do [LRCLIB](https://lrclib.net). Letras sincronizadas destacam a linha atual e permitem pular para ela.
- ▶ **YouTube**: cole um link e toque só o áudio, em qualquer uma das saídas.

## Instalação (Termux)

```bash
pkg install python mpv
pip install mutagen yt-dlp      # opcionais: tags/capas embutidas e YouTube
termux-setup-storage            # dá acesso a ~/storage/music
git clone https://github.com/GustavoPintari/MusicWeb
cd MusicWeb
```

Python 3.11 ou mais novo (por causa do `config.toml`).

## Uso

```bash
python server.py                       # usa a configuração / ~/storage/music
python server.py ~/storage/music --port 8080
python -m musicweb --config ~/meu-config.toml
```

Depois abra `http://<ip-do-celular>:8080` em qualquer aparelho da mesma rede.

## Configuração

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
| `[library] music_dir` | `~/storage/music` | pasta das músicas |
| `[library] rescan_every` | `60` | segundos entre buscas por músicas novas (0 desliga) |
| `[library] trash_dir` | *(ao lado da biblioteca)* | para onde vão os álbuns removidos |
| `[mpv] audio_output` | `opensles` | saída de áudio do mpv (`--ao`) |
| `[covers] online` | `true` | busca capas na internet |
| `[lyrics] online` | `true` | busca letras no LRCLIB |
| `[youtube] cookies` | *(vazio)* | `cookies.txt` caso o YouTube peça login |
| `[youtube] max_history` | `50` | vídeos guardados em "Tocados recentemente" |
| `[youtube] format` | m4a / melhor áudio | formato pedido ao yt-dlp |
| `[cache] dir` | `~/.cache/musicweb` | capas, letras e histórico do YouTube |

**Prioridade:** padrão < `config.toml` < variáveis de ambiente < linha de comando.
As variáveis antigas continuam valendo: `MPV_AO`, `COVERS_ONLINE`, `LYRICS_ONLINE`, `RESCAN_EVERY`, `PLAYER_NAME`, `YT_COOKIES`, `TRASH`, `MUSIC_DIR`.

## Organização das músicas

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

## Letras

Ao tocar no botão **🎤 Letra**, o servidor procura, nesta ordem:

1. arquivo `.lrc` ou `.txt` com o mesmo nome da música;
2. letra gravada nas tags (ID3 `USLT`, `LYRICS`, `©lyr`);
3. LRCLIB, pelo artista, nome da faixa, álbum e duração.

Se vier a letra errada (ou nenhuma), use **"Buscar outra"** para corrigir artista/música. As letras encontradas ficam no cache.

## YouTube

Precisa do `yt-dlp`. O áudio passa pelo próprio servidor (`/api/stream/yt_<id>`), que renova o link do YouTube quando ele expira — assim funciona tanto no mpv quanto no navegador.

Se aparecer *"o YouTube pediu login para confirmar que não é um robô"*:

1. atualize o yt-dlp: `pip install -U yt-dlp`;
2. se continuar, exporte os cookies do YouTube ([como fazer](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)) e configure `[youtube] cookies = "~/cookies.txt"`.

## Estrutura do projeto

```
server.py               atalho: python server.py
config.example.toml     modelo de configuração
musicweb/
├── app.py              inicialização (argumentos, configuração, threads)
├── config.py           leitura do config.toml / ambiente
├── state.py            estado compartilhado (biblioteca, fila, histórico do YouTube)
├── library.py          varredura da pasta, agrupamento em álbuns, atualização automática
├── covers.py           capas locais, embutidas e online; troca de capa
├── player.py           controle do mpv (fila, eventos, status)
├── editor.py           edição de tags e remoção de álbuns
├── youtube.py          yt-dlp, links diretos e histórico
├── lyrics.py           letras (.lrc, tags, LRCLIB)
├── web.py              servidor HTTP: rotas da API, streaming e downloads
├── util.py             funções pequenas compartilhadas
└── static/index.html   a página (HTML, CSS e JS num arquivo só)
```

Dependências entre módulos (sem ciclos): `config` → `state`/`util` → `youtube` → `covers` → `library` / `player` / `lyrics` → `editor` → `web` → `app`.

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/library` | álbuns, faixas e histórico do YouTube |
| GET | `/api/status` | o que o mpv está tocando |
| GET | `/api/stream/<id>` | áudio da faixa (com Range; `?dl` para baixar) |
| GET | `/api/download/<álbum>` | álbum em `.zip` |
| GET | `/api/cover/<álbum>` | capa |
| GET | `/api/cover_search?q=` | sugestões de capa |
| GET | `/api/lyrics?id=[&artist=&title=]` | letra |
| POST | `/api/play` `{album}` ou `{id, t}` | toca no mpv |
| POST | `/api/pause`, `/resume`, `/stop`, `/next`, `/prev` | controles |
| POST | `/api/seek` `{t}` · `/api/volume` `{v}` ou `{delta}` | posição e volume |
| POST | `/api/rescan` | relê a biblioteca |
| POST | `/api/edit` · `/api/delete` | editar tags · remover álbum |
| POST | `/api/cover_set` `{album, url}` · `/api/cover_upload?album=` | trocar capa |
| POST | `/api/yt` `{url}` · `/api/yt_remove` `{id}` | YouTube |

## Licença

[MIT](LICENSE)
