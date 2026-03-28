# Floorplan da Casa

## Arquivos principais
- www/floorplan/rogaciano.svg: copia publicada do SVG da casa, com IDs normalizados para camera.varanda, lampada.terraco1 e lampada.terraco2.
- www/floorplan/rogaciano.css: regras visuais do painel.
- www/floorplan/floorplan.js: frontend do ha-floorplan instalado manualmente.
- floorplan/floorplan.yaml: regras do ha-floorplan.
- floorplan/mapeamento.yaml: relacao SVG -> entidades do Home Assistant.
- floorplan/helpers_ambientes.yaml: helpers para todos os ambientes do SVG.
- floorplan/helpers_dispositivos.yaml: placeholders para os dispositivos ainda sem entidade real.
- ui-floorplan.yaml: dashboard dedicado Casa - Floorplan.

## Dispositivos reais aproveitados
### Tapo
- camera.rua -> camera.rua_tcp
- camera.varanda -> camera.varanda_visualizacao_ao_vivo

### Tuya
- lampada.garagem -> switch.garagem_interruptor_1
- lampada.piscina1 -> switch.pisicina1_interruptor_1
- lampada.piscina2 -> switch.piscina2_interruptor_1
- lampada.piscina3 -> switch.pisicina3_interruptor_1
- lampada.piscina4 -> switch.pisicina4_interruptor_1
- lampada.terraco1 -> switch.terraco1_interruptor_1
- lampada.terraco2 -> switch.terraco2_interruptor_1
- lampada.terraco3 -> switch.terraco3_interruptor_1
- lampada.quarto_vroou -> light.ventilador_do_vroou
- ventilador.quarto_vroou -> fan.ventilador_do_vroou

### Outras integracoes
- televisao.quarto_vroou -> media_player.quarto_do_vroou

## Pendencias documentadas
- lampada.escada ainda esta em helper (input_select.floorplan_estado_lampada_escada).
- arcondicionado.quarto_vroou ainda esta em helper (input_select.floorplan_estado_arcondicionado_quarto_vroou).
- A etapa de Chromecast fica para depois do floorplan estabilizado dentro do Home Assistant.