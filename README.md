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

## Observacoes

- O cast atual usa `CAST_MODE=direct`.
- O dashboard atualiza cameras em intervalo rapido.
- O floorplan usa estados reais do Home Assistant.
- O projeto foi ajustado para manter o fluxo estavel no Chromecast antes de buscar refinamentos visuais.
