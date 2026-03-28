# Rogaciano

Projeto privado de Home Assistant em Docker no Windows, com um dashboard customizado para TV que combina:

- floorplan da casa
- cameras Tapo
- envio automatico para Chromecast via `castwall`

## Stack

- `homeassistant`
  - container principal do Home Assistant
  - configuracao persistida em `config/`

- `castwall`
  - servico Flask customizado em `8090`
  - captura snapshots RTSP
  - monta a pagina do dashboard
  - envia o dashboard para o Chromecast

## Estrutura

- `docker-compose.yml`
  - sobe `homeassistant` e `castwall`

- `castwall/`
  - codigo do servico responsavel pelo dashboard da TV

- `config/`
  - configuracao versionada do Home Assistant
  - dashboards YAML
  - floorplan
  - mapeamentos dos ambientes e dispositivos

- `scripts/`
  - utilitarios de startup e atualizacao de rede

- `media/`
  - arquivos locais montados no Home Assistant

## Como subir

1. Copie [`.env.example`](C:/HomeAssistant/.env.example) para `.env.local`.
2. Ajuste os valores locais no `.env.local`.
3. Rode:

```powershell
docker compose up -d
```

Depois abra:

- `http://localhost:8123`

## Variaveis locais

Os dados sensiveis e especificos da maquina ficam em `.env.local`, por exemplo:

- IP e nome do Chromecast
- URLs publicas do `castwall`
- RTSP das cameras
- intervalos de refresh

O arquivo [`.env.example`](C:/HomeAssistant/.env.example) mostra o formato esperado.

## Fluxo atual

1. O Home Assistant chama `rest_command.cast_camera_wall_start`.
2. O `castwall` localiza o Chromecast.
3. O `castwall` gera a pagina com floorplan + cameras.
4. O Chromecast abre a URL servida pelo `castwall`.
5. As cameras atualizam por snapshot rapido.
6. O floorplan recebe estados do Home Assistant e atualiza a interface.

## Indicadores de estado

O dashboard agora diferencia melhor estado funcional e qualidade do dado:

- dispositivos `unavailable` continuam distintos dos dispositivos realmente `off`
- cameras mostram badge discreto de status: `Ao vivo`, `Atrasada` ou `Offline`
- cada camera mostra tambem o ultimo frescor do snapshot, como `Atualizada ha 3s`
- os icones `camera.*` no floorplan acompanham esse mesmo estado com classes dedicadas

## Perfis de qualidade

O dashboard da TV agora tem tres perfis operacionais:

- `economy`
  - snapshots a cada `10s`
  - refresh visual a cada `10s`
  - largura de snapshot `720`

- `normal`
  - snapshots a cada `3s`
  - refresh visual a cada `3s`
  - largura de snapshot `960`

- `near_live`
  - snapshots a cada `1s`
  - refresh visual a cada `1s`
  - largura de snapshot `960`

O perfil padrao de boot pode ser definido por:

- `DEFAULT_QUALITY_PROFILE`

No dia a dia, a troca de perfil deve ser feita sem editar `.env.local`, usando:

- `script.perfil_dashboard_tv_economia`
- `script.perfil_dashboard_tv_normal`
- `script.perfil_dashboard_tv_quase_live`

O `castwall` persiste o ultimo perfil aplicado e recasta o dashboard automaticamente quando a TV ja estiver ativa.

## Auto-start da TV

O helper `input_boolean.auto_iniciar_dashboard_tv` controla se o Home Assistant deve iniciar o dashboard automaticamente quando o `media_player.quarto_do_vroou` volta de `unavailable`/`unknown` para um estado acessivel, incluindo `off` quando o Chromecast acorda ocioso.

Quando esse helper esta ligado, a automacao `TV - Auto iniciar dashboard das cameras` espera alguns segundos para o Chromecast estabilizar antes de chamar `script.mostrar_cameras_na_tv`. O castwall watchdog continua responsavel apenas por manter uma sessao ja iniciada.

## Rede

Este projeto precisa conviver com dois cenarios:

- `Ethernet`
  - usado para trabalho normal da maquina

- `Wi-Fi`
  - usado para alcancar Chromecast e dispositivos da rede mesh

O script [Update-CastwallNetworkState.ps1](C:/HomeAssistant/scripts/Update-CastwallNetworkState.ps1) escolhe o melhor IPv4 do host e publica esse estado para o `castwall`.

No estado atual validado:

- o `castwall` prefere o IP do `Wi-Fi` quando ele estiver na mesma sub-rede do Chromecast e das cameras
- o cast funciona mesmo com o cabo ligado ao mesmo tempo

## Arquivos principais para manutencao

- [docker-compose.yml](C:/HomeAssistant/docker-compose.yml)
- [config/configuration.yaml](C:/HomeAssistant/config/configuration.yaml)
- [config/scripts.yaml](C:/HomeAssistant/config/scripts.yaml)
- [config/floorplan/mapeamento.yaml](C:/HomeAssistant/config/floorplan/mapeamento.yaml)
- [config/www/floorplan/rogaciano.svg](C:/HomeAssistant/config/www/floorplan/rogaciano.svg)
- [config/www/floorplan/rogaciano.css](C:/HomeAssistant/config/www/floorplan/rogaciano.css)
- [castwall/app.py](C:/HomeAssistant/castwall/app.py)

## Publicacao no GitHub

Este repositorio foi preparado para uso privado.

Entram no Git:

- codigo do `castwall`
- configuracoes versionadas do Home Assistant
- floorplan real
- dashboards, helpers, mapeamentos e scripts do projeto
- documentacao tecnica

Ficam fora do Git:

- `.env.local`
- `config/.storage/`
- `config/.cache/`
- bancos e logs do Home Assistant
- artefatos gerados em `config/www/castwall/`

## Fluxo do repositorio

A partir de `28/03/2026`, toda tarefa nova deste projeto deve ser trabalhada em PR.

Fluxo combinado:

- criar uma branch a partir de `main`
- usar prefixo `codex/` no nome da branch
- implementar e validar a tarefa na branch
- abrir PR para acompanhar o escopo e o diff
- so depois fazer merge em `main`

`main` deve continuar sendo a branch estavel do projeto.

## Documentacao complementar

- [CASTWALL-ARCHITECTURE.md](C:/HomeAssistant/CASTWALL-ARCHITECTURE.md)

## Comandos uteis

Subir a stack:

```powershell
docker compose up -d
```

Rebuild do `castwall`:

```powershell
docker compose up -d --build castwall
```

Atualizar o IP publicado para o Chromecast:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Update-CastwallNetworkState.ps1
```

Consultar o perfil atual do `castwall`:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8090/api/profile
```

Trocar o perfil por API local:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8090/api/profile/normal
```

## Observacoes

- O cast atual usa `CAST_MODE=direct`.
- O dashboard atualiza cameras em intervalo rapido.
- O floorplan usa estados reais do Home Assistant.
- O castwall monitora a sessao e tenta recuperar o DashCast automaticamente quando a TV cai para Backdrop ou perde o app.
- O projeto foi ajustado para manter o fluxo estavel no Chromecast antes de buscar refinamentos visuais.
