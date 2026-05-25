# Castwall Architecture for SmartRogaciano

## Goal

This environment was tuned to show a camera and floorplan dashboard on the `Quarto do vroou` Chromecast, using Home Assistant running in Docker on Windows.

## Components

- `homeassistant`
  - main Home Assistant container
  - UI exposed on port `8123`
  - persistent data stored in `config/`

- `castwall`
  - Flask service exposed on port `8090`
  - captures RTSP snapshots with `ffmpeg`
  - publishes the TV dashboard page
  - sends the dashboard to Chromecast with `pychromecast`

## Current flow

1. Home Assistant calls `rest_command.cast_camera_wall_start`.
2. That `rest_command` hits `http://host.docker.internal:8090/api/cast/start`.
3. `castwall` locates the `Quarto do vroou` Chromecast.
4. `castwall` refreshes camera snapshots.
5. The Chromecast opens the page published by `castwall`.
6. `castwall` keeps the dashboard refresh loop alive in the background.

## Current cast mode

The validated primary flow uses:

- `CAST_MODE: direct`

In this mode, the Chromecast opens the `castwall` page directly on port `8090`.

## Cast watchdog

`castwall` keeps an internal watchdog for the Chromecast session.

Current behavior:

- only tries to recover the session while casting is still desired
- detects when Chromecast leaves DashCast and returns to Backdrop or another app
- automatically re-launches DashCast after session loss
- respects a manual stop, so it does not resume by itself after the user explicitly stops it

Tuning variables:

- `CAST_WATCHDOG_ENABLED`
- `CAST_WATCHDOG_INTERVAL`
- `CAST_WATCHDOG_RECOVERY_COOLDOWN`
- `CAST_WATCHDOG_START_GRACE_SECONDS`
- `CAST_DISCOVERY_TIMEOUT`
- `CAST_SOCKET_TIMEOUT`
- `CAST_SOCKET_RETRY_WAIT`
- `DASHCAST_APP_IDS`

Chromecast discovery and connection now run with short configurable timeouts. That prevents the watchdog from getting stuck for several minutes after network instability and allows automatic retries as soon as the device starts responding again.

If `start` fails because Chromecast is not back on the network yet, `castwall` no longer drops the casting intent. It keeps the session marked as desired and lets the watchdog continue recovery attempts.

## Runtime quality profiles

`castwall` supports runtime quality profiles.

Available profiles:

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

The initial process profile still comes from:

- `DEFAULT_QUALITY_PROFILE`

After boot, the active profile is persisted in:

- `config/www/castwall/runtime/profile.json`

That makes it possible to adjust dashboard behavior without rebuilds or manual environment edits.

## Main files

- `docker-compose.yml`
- `config/configuration.yaml`
- `config/scripts.yaml`
- `castwall/app.py`
- `config/floorplan/mapeamento.yaml`
- `config/www/floorplan/rogaciano.svg`
- `config/www/floorplan/rogaciano.css`

## Floorplan inside the dashboard

The current dashboard combines:

- the house floorplan on the left
- two cameras on the right
- room and device states layered on top of the SVG

The page served by `castwall` does the following:

1. embeds the SVG from `config/www/floorplan/rogaciano.svg`
2. embeds the CSS from `config/www/floorplan/rogaciano.css`
3. reads mappings from `config/floorplan/mapeamento.yaml`
4. fetches the latest states from the Home Assistant API
5. uses `config/home-assistant_v2.db` only as a fallback
6. applies CSS classes such as:
   - `room-helper-on`
   - `room-helper-off`
   - `room-light-on`
   - `device-on`
   - `device-off`
   - `device-unavailable`
   - `glare-on`

## State sources

Primary source:

- Home Assistant API at `http://homeassistant:8123`

Fallback:

- `config/home-assistant_v2.db`

Important note:

- in this Windows + Docker Desktop environment, SQLite access that worked inside the container used the `immutable=1` URI mode

## Floorplan updates

The dashboard tries to keep a continuous `GET /api/floorplan/stream` connection so state changes can appear without depending only on camera refresh cycles.

## Camera freshness indicators

`castwall` derives a status for each camera based on the last successful snapshot:

- `fresh`
  - camera is updating on schedule
  - `Live` badge on the card
  - `camera.*` icon on the floorplan uses `device-on`

- `stale`
  - the last known snapshot still exists, but it is already behind the current profile expectation
  - `Stale` badge on the card
  - `camera.*` icon on the floorplan uses `device-stale`

- `offline`
  - no recent snapshot or no initial snapshot at all
  - `Offline` badge on the card
  - `camera.*` icon on the floorplan uses `device-unavailable`

These values are exposed in two places:

- `GET /health` under `camera_status`
- `GET /api/floorplan/state` under `cameras`

Current behavior:

- preferred path: continuous event stream
- automatic fallback: lightweight polling when the Chromecast browser cannot keep the stream alive
- cameras still refresh independently according to the active profile

## Motion and detection alerts

The floorplan supports an alert pipeline that is separate from the normal room-state rendering:

- `room-alert-on`
  - paints areas with `#e9afafff`
  - visually overrides `room-light-on`

- `motion-on`
  - reveals alert-only elements that should stay hidden by default, such as `movimento.garagem`

Alert mappings live in `config/floorplan/mapeamento.yaml` under the `alertas` section.

Current state:

- `binary_sensor.garagem_movimento`
  - reveals `movimento.garagem`
  - highlights `ambiente.garagem`

- `input_boolean.alerta_camera_varanda_pessoa`
  - temporary helper used to highlight `ambiente.varanda` and `ambiente.piscina`

- `input_boolean.alerta_camera_rua_deteccao`
  - temporary helper used to highlight `ambiente.rua`

Those camera helpers exist because Home Assistant does not currently expose a live person-detected or motion-detected entity/device trigger for the Tapo `rua` and `varanda` cameras. When that real source becomes available, the only required change is to point the alert mapping to the proper `entity_id`.

## Quality profile control from Home Assistant

Home Assistant exposes three `rest_command` entries to switch profiles:

- `rest_command.cast_camera_wall_profile_economy`
- `rest_command.cast_camera_wall_profile_normal`
- `rest_command.cast_camera_wall_profile_near_live`

There is also a selector helper:

- `input_select.castwall_perfil_dashboard_tv`

And the day-to-day scripts:

- `script.perfil_dashboard_tv_economia`
- `script.perfil_dashboard_tv_normal`
- `script.perfil_dashboard_tv_quase_live`
