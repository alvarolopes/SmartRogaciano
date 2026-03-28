# Castwall Architecture

## Objetivo

Este ambiente foi ajustado para mostrar um dashboard de cameras no Chromecast `Quarto do vroou` a partir do Home Assistant rodando em Docker no Windows.

## Componentes

- `homeassistant`
  - Container principal do Home Assistant.
  - Expoe a interface em `8123`.
  - Usa `config/` como persistencia.

- `castwall`
  - Servico Flask em `8090`.
  - Captura snapshots das cameras RTSP com `ffmpeg`.
  - Mantem os snapshots em `/app/cache`.
  - Publica arquivos em `config/www/castwall`.
  - Faz o envio para o Chromecast via `pychromecast`.

## Fluxo Atual

1. O Home Assistant chama `rest_command.cast_camera_wall_start`.
2. Esse `rest_command` chama `http://host.docker.internal:8090/api/cast/start`.
3. O `castwall` localiza o Chromecast `Quarto do vroou`.
4. O `castwall` captura snapshots das cameras.
5. O `castwall` expÃµe a pÃ¡gina em `http://IP-ATIVO:8090/` e o DashCast abre essa URL diretamente.
6. O `castwall` atualiza a sessao em segundo plano.

## Modo Atual de Cast

O fluxo principal atual usa:

- `CAST_MODE: direct`

Isso e importante porque o Chromecast abre a pÃ¡gina do `castwall` diretamente em `8090`, e a prÃ³pria pÃ¡gina atualiza os snapshots a cada 1 segundo.

Esse modo foi o que funcionou de forma estavel no estado atual da rede.

## Frequencia Atual

No estado atual:

- `SNAPSHOT_INTERVAL: 1`
- `IMAGE_REFRESH_SECONDS: 1`

Ou seja, as imagens das cameras sao recapturadas e reenviadas a cada 1 segundo.

## Arquivos Principais

- [docker-compose.yml](C:/HomeAssistant/docker-compose.yml)
- [config/configuration.yaml](C:/HomeAssistant/config/configuration.yaml)
- [config/scripts.yaml](C:/HomeAssistant/config/scripts.yaml)
- [castwall/app.py](C:/HomeAssistant/castwall/app.py)
- [config/www/castwall/index.html](C:/HomeAssistant/config/www/castwall/index.html)

## Rede e Contexto Importante

Este computador nao fica sempre na mesma interface de rede.

As vezes ele esta:

- no `Ethernet`

E as vezes ele esta:

- no `Wi-Fi`

Esse detalhe ja causou confusao de IP durante a configuracao. Em `25/03/2026`, por exemplo, o estado real que funcionou foi com a maquina em `Wi-Fi`, usando IP `192.168.5.191`, enquanto o Chromecast estava em `192.168.5.137`.

## Limitacao Atual Aceita

Por agora, esta aceito deixar a configuracao assim, com comportamento funcional no estado atual.

Ainda nao foi implementado um mecanismo automatico para:

- detectar o IP ativo correto em qualquer interface
- alternar automaticamente entre `Ethernet` e `Wi-Fi`
- manter o fluxo transparente nas duas formas de conexao

## Desejo Futuro Registrado

Fica registrado como objetivo futuro:

- fazer o cast funcionar tanto no `Ethernet` quanto no `Wi-Fi`

Idealmente, no futuro, o sistema deve descobrir sozinho qual interface/IP esta valido no momento e usar isso sem ajuste manual.

## Observacoes de Manutencao

- O fluxo principal atual usa `CAST_MODE: direct`, com `PUBLIC_URL` apontando para o IP valido da rede mesh.
- Se o comportamento voltar a falhar depois de mudanca de rede, a primeira verificacao deve ser:
  - IP atual da maquina
  - interface ativa (`Ethernet` ou `Wi-Fi`)
  - conectividade com o Chromecast
  - estado do `castwall` em `/health`

## Comando Util

Para reaplicar mudancas no `castwall`:

```powershell
docker compose up -d --build castwall
```


## Floorplan Vivo no Dashboard

Em `25/03/2026`, o dashboard passou a combinar:

- planta da casa na esquerda
- duas cameras na direita
- atualizacao visual a cada 1 segundo nas cameras

A pagina servida pelo `castwall` em `http://IP-ATIVO:8090/` faz o seguinte:

1. embute o SVG da planta a partir de `config/www/floorplan/rogaciano.svg`
2. embute o CSS visual da planta a partir de `config/www/floorplan/rogaciano.css`
3. consulta os mapeamentos em `config/floorplan/mapeamento.yaml`
4. busca os estados atuais direto da API do Home Assistant
5. usa o banco `config/home-assistant_v2.db` apenas como fallback
6. aplica classes CSS no SVG, por exemplo:
   - `room-helper-on`
   - `device-on`
   - `device-off`
   - `device-unavailable`

Com isso, quando uma entidade mapeada muda de estado no Home Assistant, o indicador correspondente na planta pode mudar no dashboard sem trocar o layout principal.

## Particularidade Importante do SQLite no Docker Desktop

Neste computador com Windows + Docker Desktop, o `castwall` nao conseguiu abrir `home-assistant_v2.db` com conexao SQLite normal nem com `mode=ro` dentro do container.

O modo que funcionou foi abrir com URI `immutable=1`.

Isso significa:

- se o floorplan voltar a aparecer todo como `unavailable`, verificar primeiro a leitura do SQLite no `castwall`
- esse detalhe e especifico do ambiente atual e deve ser lembrado antes de reescrever essa parte

## Estado Atual Validado

No estado atual validado em `25/03/2026`:

- `CAST_MODE: direct`
- `PUBLIC_URL: http://192.168.5.191:8090/`
- `SNAPSHOT_INTERVAL: 1`
- `IMAGE_REFRESH_SECONDS: 1`
- layout com planta na esquerda e cameras na direita
- floorplan consumindo estados reais do Home Assistant


## Atualizacao da Planta por Evento

O dashboard agora tenta manter uma conexao continua em `GET /api/floorplan/stream` para receber mudancas do floorplan sem esperar o ciclo de 10 segundos das cameras.

Fonte atual dos estados:

- primaria: API do Home Assistant em `http://homeassistant:8123` usando token local lido de `config/.storage/auth`
- fallback: `config/home-assistant_v2.db` quando a API nao responder

Comportamento atual:

- caminho preferencial: stream continuo de eventos do `castwall`
- fallback automatico: consulta rapida ao estado da planta se o navegador do Chromecast nao sustentar o stream
- cameras continuam no ciclo proprio de `1s`


## Runtime de Rede do Host

Em `25/03/2026`, o `castwall` passou a aceitar um estado de rede externo em tempo de execucao, lido de:

- `config/www/castwall/runtime/network.json`

Esse arquivo e escrito no Windows pelo script:

- `scripts/Update-CastwallNetworkState.ps1`

E o startup principal agora chama esse script antes de subir os containers:

- `scripts/Start-HomeAssistant.ps1`

### Regra Atual de Escolha

Quando existem `Ethernet` e `Wi-Fi` ativos ao mesmo tempo, o script:

- lista os IPv4 ativos reais da maquina
- ignora interfaces virtuais como `Hyper-V` e `WSL`
- le os IPs dos alvos no `docker-compose.yml`
- prefere a interface que estiver na mesma sub-rede dos dispositivos
- favorece `Wi-Fi` quando ele bater com Chromecast e cameras

No estado validado de `25/03/2026`, isso escolheu:

- `Wi-Fi`
- IP `192.168.5.191`

Mesmo com o cabo ativo em `192.168.15.142`.

### Efeito no Castwall

O `castwall` continua com `PUBLIC_URL` configurado no ambiente, mas no `cast/start` ele pode sobrescrever o host usando o `selected_ip` do `network.json`.

Com isso, o fluxo esperado passa a ser:

- trabalho normal pelo cabo
- dashboard do Chromecast publicado pelo IP do `Wi-Fi`
- cameras e Chromecast alcancados pela rede mesh

### Comando Manual Util

Se a rede mudar sem reiniciar o Home Assistant, o estado pode ser atualizado manualmente com:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\HomeAssistant\scripts\Update-CastwallNetworkState.ps1
```


