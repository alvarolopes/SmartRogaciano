# Rogaciano

A personal smart home project built to prove that a useful home automation stack does not need expensive infrastructure or a fully integrated ecosystem from day one.

This repository documents my Home Assistant setup running on Docker for Windows, combining low-cost devices, custom glue code, and incremental automation work into a practical smart house dashboard for daily use.

The main goal is simple: take a house with only a few connected devices, integrate them automatically, expose real device state, and turn that into a system that is reliable enough to use on a TV, not just in an admin panel.

## What the project does

- runs Home Assistant in Docker with persistent configuration
- renders a house floorplan with live device state overlays
- integrates Tapo cameras and Tuya devices
- builds a TV-friendly dashboard for cameras and floorplan status
- casts that dashboard to a Chromecast through a custom local service
- handles mixed network scenarios where the host uses both Ethernet and Wi-Fi

## Why this exists

This is a personal project focused on building a smart home with limited resources and gradually connected devices.

Instead of waiting for a perfect ecosystem, the approach here is to:

- integrate what already exists in the house
- normalize state across different vendors
- automate the boring parts
- build a dashboard that is clear enough for real everyday use
- keep everything maintainable in plain files under version control

## Technical stack

### Core platform

- `Home Assistant`
- `Docker Compose`
- `Windows host`

### Device integrations

- `TP-Link Tapo` for cameras
- `Tuya` for switches, fan/light modules, and sensors
- `Google Cast / Chromecast` for TV display workflows

### Custom services

- `castwall`
  - custom Flask service
  - captures RTSP snapshots with `ffmpeg`
  - assembles the TV dashboard page
  - sends the dashboard to Chromecast with `pychromecast`

### Frontend and dashboard

- `ha-floorplan`
- `SVG` floorplan
- `YAML` dashboards
- custom CSS state styling

## Current architecture

The stack currently revolves around two main services:

- `homeassistant`
  - main Home Assistant container
  - persistent configuration stored in `config/`

- `castwall`
  - lightweight local service exposed on port `8090`
  - grabs camera snapshots
  - merges camera data with floorplan state
  - serves a TV-ready dashboard
  - controls dashboard casting to Chromecast

## Dashboard behavior

The TV dashboard combines:

- the house floorplan on one side
- camera panels on the other side
- real-time device state styling on top of the SVG

State visualization is intentionally simple and operational:

- active devices are highlighted clearly
- powered-off devices stay visually neutral
- unavailable or offline devices remain easy to distinguish
- cameras expose freshness status such as live, stale, or offline

## Quality profiles

The dashboard supports runtime quality profiles so the same project can balance stability and responsiveness depending on the device and network quality.

Available profiles:

- `economy`
- `normal`
- `near_live`

These profiles change snapshot cadence, refresh interval, and image resolution without forcing a rebuild.

## Floorplan and smart house model

The floorplan is backed by a real SVG representation of the house and is mapped to Home Assistant entities through YAML.

The project currently includes:

- room helpers for full floorplan coverage
- device-to-SVG mapping files
- visual rules for lights, cameras, fans, climate placeholders, and media entities
- alert overlays for motion and camera-related attention states

This makes the system useful even when some rooms or devices are not fully automated yet.

## Network constraints handled by the project

One of the practical challenges in this setup is that the machine may use:

- `Ethernet` for normal work
- `Wi-Fi` for Chromecast and mesh-network smart devices

Because of that, the project includes scripts that detect the best local IPv4 path for casting and keep the local dashboard reachable by the Chromecast without manual reconfiguration every time the network context changes.

## Repository structure

- `docker-compose.yml`
  - starts `homeassistant` and `castwall`

- `config/`
  - versioned Home Assistant configuration
  - dashboards
  - floorplan files
  - mappings, helpers, scripts, and YAML definitions

- `castwall/`
  - source code for the custom Chromecast dashboard service

- `scripts/`
  - local utility scripts for startup and network updates

- `media/`
  - local media mounted into Home Assistant

## Run locally

1. Copy `.env.example` to `.env.local`
2. Adjust local values in `.env.local`
3. Start the stack:

```powershell
docker compose up -d
```

Then open:

- `http://localhost:8123`

## Local environment variables

Sensitive and machine-specific values live in `.env.local`, including:

- Chromecast name and IP
- public URL used by `castwall`
- camera RTSP endpoints
- refresh intervals and quality profile defaults

`.env.example` shows the expected format.

## Repository policy

This repository is prepared for private use and versioned maintenance.

Included in Git:

- `castwall` source code
- versioned Home Assistant configuration
- floorplan assets
- dashboards, mappings, helpers, and scripts
- technical documentation

Excluded from Git:

- `.env.local`
- `config/.storage/`
- `config/.cache/`
- Home Assistant databases and logs
- generated runtime artifacts under `config/www/castwall/`

## Main files to maintain

- `docker-compose.yml`
- `config/configuration.yaml`
- `config/scripts.yaml`
- `config/floorplan/mapeamento.yaml`
- `config/www/floorplan/rogaciano.svg`
- `config/www/floorplan/rogaciano.css`
- `castwall/app.py`

## Additional documentation

- `CASTWALL-ARCHITECTURE.md`

## Notes

- the current casting path uses `CAST_MODE=direct`
- the dashboard is optimized for practical stability before visual perfection
- the floorplan is driven by real Home Assistant state whenever possible
- the project is intentionally incremental: devices can be replaced, remapped, or upgraded over time without redesigning the whole system