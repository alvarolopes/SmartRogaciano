# Castwall Architecture

## Objetivo

Este ambiente foi ajustado para mostrar um dashboard de cameras no Chromecast `Quarto do vroou` a partir do Home Assistant rodando em Docker no Windows.

## Componentes

- `homeassistant`
  - container principal do Home Assistant
  - interface exposta em `8123`
  - persistencia em `config/`

- `castwall`
  - servico Flask em `8090`
  - captura snapshots das cameras RTSP com `ffmpeg`
  - publica a pagina da TV
  - faz o envio para o Chromecast via `pychromecast`

## Fluxo atual

1. O Home Assistant chama `rest_command.cast_camera_wall_start`.
2. O `rest_command` aciona `http://host.docker.internal:8090/api/cast/start`.
3. O `castwall` localiza o Chromecast `Quarto do vroou`.
4. O `castwall` atualiza snapshots das cameras.
5. O Chromecast abre a pagina publicada pelo `castwall`.
6. O `castwall` mantem o refresh do dashboard em segundo plano.

## Modo de cast atual

O fluxo principal validado usa:

- `CAST_MODE: direct`

Nesse modo, o Chromecast abre a pagina do `castwall` diretamente na porta `8090`.

## Watchdog de cast

O castwall mantem um watchdog interno para a sessao do Chromecast.

Comportamento atual:

- so tenta recuperar a sessao quando o cast continua desejado
- detecta quando o Chromecast sai do DashCast e volta para Backdrop ou outro app
- tenta relancar o DashCast automaticamente apos perda de sessao
- respeita stop manual, ou seja, nao religa sozinho quando o usuario mandar parar

Variaveis de ajuste:

- `CAST_WATCHDOG_ENABLED`
- `CAST_WATCHDOG_INTERVAL`
- `CAST_WATCHDOG_RECOVERY_COOLDOWN`
- `CAST_WATCHDOG_START_GRACE_SECONDS`
- `DASHCAST_APP_IDS`

## Frequencia atual

O `castwall` agora suporta perfis de qualidade em runtime.

Perfis disponiveis:

- `economy`
  - `snapshot_interval: 10`
  - `image_refresh_seconds: 10`
  - `snapshot_width: 720`

- `normal`
  - `snapshot_interval: 3`
  - `image_refresh_seconds: 3`
  - `snapshot_width: 960`

- `near_live`
  - `snapshot_interval: 1`
  - `image_refresh_seconds: 1`
  - `snapshot_width: 960`

O perfil inicial do processo continua vindo de:

- `DEFAULT_QUALITY_PROFILE`

Depois do boot, o perfil ativo fica persistido em:

- `config/www/castwall/runtime/profile.json`

Isso permite trocar o comportamento do dashboard sem rebuild nem edicao manual de ambiente.

## Arquivos principais

- [docker-compose.yml](C:/HomeAssistant/docker-compose.yml)
- [config/configuration.yaml](C:/HomeAssistant/config/configuration.yaml)
- [config/scripts.yaml](C:/HomeAssistant/config/scripts.yaml)
- [castwall/app.py](C:/HomeAssistant/castwall/app.py)
- [config/floorplan/mapeamento.yaml](C:/HomeAssistant/config/floorplan/mapeamento.yaml)
- [config/www/floorplan/rogaciano.svg](C:/HomeAssistant/config/www/floorplan/rogaciano.svg)
- [config/www/floorplan/rogaciano.css](C:/HomeAssistant/config/www/floorplan/rogaciano.css)

## Floorplan no dashboard

O dashboard atual combina:

- planta da casa na esquerda
- duas cameras na direita
- estados dos ambientes e dispositivos sobrepostos ao SVG

A pagina servida pelo `castwall` faz o seguinte:

1. embute o SVG a partir de `config/www/floorplan/rogaciano.svg`
2. embute o CSS a partir de `config/www/floorplan/rogaciano.css`
3. consulta os mapeamentos em `config/floorplan/mapeamento.yaml`
4. busca os estados atuais na API do Home Assistant
5. usa `config/home-assistant_v2.db` apenas como fallback
6. aplica classes CSS como:
   - `room-helper-on`
   - `room-helper-off`
   - `room-light-on`
   - `device-on`
   - `device-off`
   - `device-unavailable`
   - `glare-on`

## Fonte dos estados

Fonte principal:

- API do Home Assistant em `http://homeassistant:8123`

Fallback:

- `config/home-assistant_v2.db`

Observacao importante:

- neste ambiente Windows + Docker Desktop, a leitura SQLite que funcionou no container foi com URI `immutable=1`

## Atualizacao da planta

O dashboard tenta manter uma conexao continua em `GET /api/floorplan/stream` para refletir mudancas de estado sem depender apenas do ciclo das cameras.

## Indicadores de frescor das cameras

O `castwall` agora calcula um estado derivado para cada camera com base no ultimo snapshot bem-sucedido:

- `fresh`
  - camera atualizando no ritmo esperado
  - badge `Ao vivo` no card
  - icone `camera.*` no floorplan fica em `device-on`

- `stale`
  - camera ainda tem ultimo snapshot conhecido, mas ja esta atrasada para o perfil atual
  - badge `Atrasada` no card
  - icone `camera.*` no floorplan fica em `device-stale`

- `offline`
  - camera sem snapshot recente ou sem snapshot inicial
  - badge `Offline` no card
  - icone `camera.*` no floorplan fica em `device-unavailable`

Esses dados saem em dois lugares:

- `GET /health` em `camera_status`
- `GET /api/floorplan/state` em `cameras`

Comportamento atual:

- caminho preferencial: stream continuo de eventos
- fallback automatico: consulta rapida de estado quando o navegador do Chromecast nao sustenta o stream
- cameras continuam em refresh proprio conforme o perfil ativo

## Controle de perfis pelo Home Assistant

O Home Assistant expoe tres `rest_command` para troca de perfil:

- `rest_command.cast_camera_wall_profile_economy`
- `rest_command.cast_camera_wall_profile_normal`
- `rest_command.cast_camera_wall_profile_near_live`

Tambem existe um helper de selecao:

- `input_select.castwall_perfil_dashboard_tv`

E os scripts de uso diario:

- `script.perfil_dashboard_tv_economia`
- `script.perfil_dashboard_tv_normal`
- `script.perfil_dashboard_tv_quase_live`

O fluxo esperado e:

1. selecionar o perfil desejado no helper ou por script
2. chamar o `rest_command` correspondente
3. o `castwall` persistir o perfil
4. se o cast estiver ativo, recastar a pagina automaticamente

## Start automatico apos ligar a TV

O inicio automatico do dashboard mora no Home Assistant, nao no castwall. O helper `input_boolean.auto_iniciar_dashboard_tv` permite desligar esse comportamento sem editar arquivos.

A automacao `TV - Auto iniciar dashboard das cameras` observa `media_player.quarto_do_vroou` voltando de `unavailable`/`unknown` para um estado acessivel. Isso inclui o retorno para `off`, que neste Chromecast significa estado ocioso e pronto para receber o dashboard. Depois disso ela aplica um atraso curto e chama `script.mostrar_cameras_na_tv`.

Separacao de responsabilidades:

- Home Assistant detecta o momento certo de iniciar o cast.
- O watchdog do castwall mantem o DashCast vivo depois que a sessao ja existe.

## Runtime de rede do host

Este computador pode operar de duas formas:

- com `Ethernet`
- com `Wi-Fi`

Como Chromecast e cameras estao na rede mesh, o `castwall` precisa publicar o dashboard no IP correto do host.

Para isso, existe um estado de rede externo lido em:

- `config/www/castwall/runtime/network.json`

Esse arquivo e gerado pelo script:

- [Update-CastwallNetworkState.ps1](C:/HomeAssistant/scripts/Update-CastwallNetworkState.ps1)

E o startup principal chama esse script antes de subir os containers:

- [Start-HomeAssistant.ps1](C:/HomeAssistant/scripts/Start-HomeAssistant.ps1)

## Regra atual de escolha de IP

Quando `Ethernet` e `Wi-Fi` estao ativos ao mesmo tempo, o script:

- lista os IPv4 reais da maquina
- ignora interfaces virtuais como `Hyper-V` e `WSL`
- considera os alvos configurados para Chromecast e cameras
- prefere a interface na mesma sub-rede dos dispositivos
- favorece `Wi-Fi` quando ele bate com Chromecast e cameras

No estado validado, isso escolheu:

- `Wi-Fi`
- IP `192.168.5.191`

Mesmo com o cabo ativo em `192.168.15.142`.

## Efeito pratico

Com isso, o fluxo esperado fica assim:

- trabalho normal da maquina pode continuar pelo cabo
- o dashboard do Chromecast e publicado pelo IP do `Wi-Fi`
- cameras e Chromecast continuam alcancaveis pela rede mesh

## Estado atual validado

No estado atual:

- `CAST_MODE: direct`
- `PUBLIC_URL: http://192.168.5.191:8090/`
- perfis `economy`, `normal` e `near_live` funcionando
- floorplan ativo no dashboard
- layout com planta na esquerda e cameras na direita
- cast funcionando no `Quarto do vroou`

## Fluxo do repositorio

A partir de `28/03/2026`, toda tarefa nova deve seguir fluxo por PR.

Regra de trabalho:

- criar branch a partir de `main`
- usar prefixo `codex/`
- implementar e validar fora de `main`
- abrir PR para acompanhamento
- mergear em `main` somente depois

Isso passa a fazer parte do contexto de manutencao deste projeto.

## Comandos uteis

Rebuild do `castwall`:

```powershell
docker compose up -d --build castwall
```

Consultar o perfil atual:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8090/api/profile
```

Trocar o perfil atual:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8090/api/profile/economy
```

Atualizar o estado de rede sem reiniciar tudo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\HomeAssistant\scripts\Update-CastwallNetworkState.ps1
```

## Pendencia futura registrada

Objetivo futuro:

- deixar o cast funcionar de forma transparente tanto no `Ethernet` quanto no `Wi-Fi`, sem depender de ajuste manual
