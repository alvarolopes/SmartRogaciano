# Home Assistant em Docker no Windows

Esta pasta deixa uma base pronta para rodar o Home Assistant em Docker com persistencia em disco, restart automatico do container e um ponto de partida para:

- conectar cameras Tapo
- montar um dashboard para TV
- enviar esse dashboard para o Chromecast

## O que foi criado

- `docker-compose.yml`: stack principal do Home Assistant
- `config/`: configuracao persistente do Home Assistant
- `media/`: pasta para arquivos locais de midia
- `scripts/Start-HomeAssistant.ps1`: sobe a stack e espera o Docker ficar pronto
- `HomeAssistantStartup.cmd`: launcher simples para colocar no startup do Windows
- `Register-HomeAssistantStartupTaskAtLogon.ps1`: tentativa de registro por tarefa agendada

O bind mount `./config:/config` e o que garante que suas configuracoes sobrevivam ao reinicio do PC e do container.

## Antes de subir

1. Confirme no Docker Desktop que ele esta configurado para iniciar com o Windows.
2. Deixe o Docker em modo Linux containers.
3. Copie `.env.example` para `.env.local` e ajuste os valores locais, especialmente IPs, URLs e credenciais RTSP.

## Como subir

No PowerShell, dentro desta pasta:

```powershell
docker compose up -d
```

Depois abra:

- `http://localhost:8123`

## Como garantir que volte depois do reboot

O `restart: unless-stopped` reinicia o container quando o Docker volta.

No Windows, o ponto importante e o Docker Desktop iniciar sozinho. A forma mais simples de reforcar isso e colocar `HomeAssistantStartup.cmd` na pasta Startup do usuario.

Como alternativa, voce tambem pode tentar a tarefa agendada:

```powershell
powershell -ExecutionPolicy Bypass -File .\Register-HomeAssistantStartupTaskAtLogon.ps1
```

Isso cria uma tarefa para executar `.\scripts\Start-HomeAssistant.ps1` no logon.

## Fluxo recomendado para o seu caso

### 1. Adicionar as cameras Tapo

1. Configure as cameras primeiro no app oficial Tapo.
2. No Home Assistant, va em `Settings > Devices & services`.
3. Adicione a integracao `Tapo`.
4. Se a descoberta automatica falhar, faca a configuracao manual.

### 2. Adicionar o Chromecast

1. No Home Assistant, adicione a integracao `Google Cast`.
2. Se ele nao aparecer automaticamente, informe o IP manualmente em `Known hosts`.

### 3. Ajustar o dashboard da TV

Edite:

- `config/ui-lovelace-cast.yaml`

Troque os exemplos:

- `camera.camera_frente`
- `camera.camera_garagem`
- `camera.camera_portao`
- `camera.camera_quintal`

pelos `entity_id` reais das suas cameras.

### 4. Ajustar o script que faz o cast

Edite:

- `config/scripts.yaml`

Troque:

- `media_player.seu_chromecast`

pelo `entity_id` real do seu Chromecast ou da sua TV com Google Cast.

## Limitacoes importantes

### Windows + Docker Desktop

O Home Assistant documenta Windows principalmente via maquina virtual. A instalacao em container funciona, mas no Windows a descoberta de dispositivos na rede pode ser menos confiavel do que em Linux com `network_mode: host`.

Na pratica:

- Tapo pode precisar de configuracao manual
- Chromecast pode precisar de IP manual
- algumas descobertas automaticas podem falhar

### Dashboard de cameras no Chromecast

O cast nativo do Home Assistant e bom para dashboards, mas pode ter limitacoes com video ao vivo de cameras.

Se o objetivo for uma grade de cameras 100% ao vivo e sempre estavel na TV, a opcao mais forte costuma ser uma destas:

- rodar o Home Assistant OS em VM no Windows
- rodar o Home Assistant em um mini PC, Raspberry Pi ou Home Assistant Green
- abrir o dashboard em um navegador e espelhar a aba para a TV

## Arquivos que voce provavelmente vai editar

- `config/scripts.yaml`
- `config/ui-lovelace-cast.yaml`
- `config/configuration.yaml`

## Publicacao no GitHub

Este projeto esta preparado para um repositorio privado no GitHub.

Entram no Git:

- codigo do `castwall`
- configuracoes versionadas do Home Assistant
- floorplan real em `config/www/floorplan/`
- mapeamentos, helpers, dashboards e scripts do projeto
- documentacao da arquitetura

Ficam fora do Git por `.gitignore`:

- `.env.local`
- `config/.storage/`
- `config/.cache/`
- bancos e logs do Home Assistant
- artefatos publicados do `config/www/castwall/`

Use `.env.local` para credenciais, IPs, URLs e outros dados que mudam de maquina para maquina.

## Proximo passo sugerido

1. Subir o container.
2. Fazer o onboarding do Home Assistant.
3. Integrar Tapo e Google Cast.
4. Descobrir os `entity_id` reais.
5. Ajustar `scripts.yaml` e `ui-lovelace-cast.yaml`.

