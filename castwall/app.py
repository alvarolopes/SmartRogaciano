import base64
import json
import logging
import os
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from flask import Flask, Response, jsonify, make_response, send_file
import pychromecast
from pychromecast.controllers.dashcast import DashCastController
import yaml

APP = Flask(__name__)
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').strip().upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
CACHE_DIR = Path('/app/cache')
PUBLIC_DIR = Path(os.environ.get('PUBLIC_DIR', '/app/public'))
HA_CONFIG_DIR = Path(os.environ.get('HA_CONFIG_DIR', '/ha-config'))
FLOORPLAN_SVG_PATH = HA_CONFIG_DIR / 'www' / 'floorplan' / 'rogaciano.svg'
FLOORPLAN_CSS_PATH = HA_CONFIG_DIR / 'www' / 'floorplan' / 'rogaciano.css'
FLOORPLAN_MAP_PATH = HA_CONFIG_DIR / 'floorplan' / 'mapeamento.yaml'
HOST_NETWORK_STATE_PATH = HA_CONFIG_DIR / 'www' / 'castwall' / 'runtime' / 'network.json'
HA_DB_PATH = HA_CONFIG_DIR / 'home-assistant_v2.db'
HA_AUTH_PATH = HA_CONFIG_DIR / '.storage' / 'auth'
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_INTERVAL = float(os.environ.get('SNAPSHOT_INTERVAL', '2'))
CHROMECAST_KNOWN_HOSTS = [
    host.strip()
    for host in os.environ.get('CHROMECAST_KNOWN_HOSTS', os.environ.get('CHROMECAST_IP', '')).split(',')
    if host.strip()
]
CHROMECAST_NAME = os.environ.get('CHROMECAST_NAME', '').strip()
PUBLIC_URL = os.environ['PUBLIC_URL']
CAST_MODE = os.environ.get('CAST_MODE', 'embedded').strip().lower()
PAGE_REFRESH_SECONDS = int(os.environ.get('PAGE_REFRESH_SECONDS', '60'))
IMAGE_REFRESH_SECONDS = int(os.environ.get('IMAGE_REFRESH_SECONDS', '3'))
FLOORPLAN_WATCH_INTERVAL = float(os.environ.get('FLOORPLAN_WATCH_INTERVAL', '1'))
FLOORPLAN_STREAM_HEARTBEAT_SECONDS = int(os.environ.get('FLOORPLAN_STREAM_HEARTBEAT_SECONDS', '15'))
SNAPSHOT_WIDTH = int(os.environ.get('SNAPSHOT_WIDTH', '960'))
CAST_START_ATTEMPTS = int(os.environ.get('CAST_START_ATTEMPTS', '4'))
CAST_START_RETRY_SECONDS = float(os.environ.get('CAST_START_RETRY_SECONDS', '4'))
CAST_READY_DELAY_SECONDS = float(os.environ.get('CAST_READY_DELAY_SECONDS', '2'))
SNAPSHOT_BASE_URL = os.environ.get('SNAPSHOT_BASE_URL', '').strip().rstrip('/')
HOME_ASSISTANT_URL = os.environ.get('HOME_ASSISTANT_URL', 'http://homeassistant:8123').strip().rstrip('/')
CAST_WATCHDOG_ENABLED = os.environ.get('CAST_WATCHDOG_ENABLED', '1').strip().lower() not in {'0', 'false', 'no', 'off'}
CAST_WATCHDOG_INTERVAL = float(os.environ.get('CAST_WATCHDOG_INTERVAL', '20'))
CAST_WATCHDOG_RECOVERY_COOLDOWN = float(os.environ.get('CAST_WATCHDOG_RECOVERY_COOLDOWN', '30'))
CAST_WATCHDOG_START_GRACE_SECONDS = float(os.environ.get('CAST_WATCHDOG_START_GRACE_SECONDS', '20'))
DASHCAST_APP_IDS = {
    app_id.strip()
    for app_id in os.environ.get('DASHCAST_APP_IDS', '84912283').split(',')
    if app_id.strip()
}
PRIMARY_DASHCAST_APP_ID = sorted(DASHCAST_APP_IDS)[0] if DASHCAST_APP_IDS else '84912283'

CAMERAS = {
    'rua': {
        'label': 'Rua',
        'rtsp_url': os.environ['CAMERA_RUA_RTSP'],
        'snapshot_path': CACHE_DIR / 'rua.jpg',
        'public_path': PUBLIC_DIR / 'rua.jpg',
    },
    'varanda': {
        'label': 'Varanda',
        'rtsp_url': os.environ['CAMERA_VARANDA_RTSP'],
        'snapshot_path': CACHE_DIR / 'varanda.jpg',
        'public_path': PUBLIC_DIR / 'varanda.jpg',
    },
}

STATE = {
    name: {
        'ok': False,
        'last_success': None,
        'last_error': 'snapshot ainda nao capturado',
    }
    for name in CAMERAS
}
CAST_STATE = {
    'active': False,
    'desired_active': False,
    'last_start': None,
    'last_refresh': None,
    'last_error': None,
    'last_watchdog_check': None,
    'last_watchdog_status': 'idle',
    'last_watchdog_reason': None,
    'last_recovery_attempt': None,
    'last_recovery_success': None,
    'recovery_count': 0,
    'recovery_failures': 0,
    'last_seen_device': None,
    'last_seen_app_id': None,
    'last_seen_display_name': None,
}
CAST_LOCK = threading.RLock()
HA_TOKEN_LOCK = threading.Lock()
HA_TOKEN_CACHE = {
    'access_token': None,
    'expires_at': 0.0,
}
DYNAMIC_FLOORPLAN_CLASSES = [
    'room-helper-on',
    'room-helper-off',
    'room-light-on',
    'room-unavailable',
    'device-on',
    'device-off',
    'device-unavailable',
    'glare-on',
]
UNAVAILABLE_STATES = {'unavailable', 'unknown', 'offline', 'none'}
DEVICE_ON_STATES = {
    'on',
    'playing',
    'paused',
    'idle',
    'cool',
    'heat',
    'fan_only',
    'dry',
    'auto',
    'streaming',
    'recording',
    'true',
}
DEVICE_OFF_STATES = {'off', 'standby', 'false'}


def _now_ts() -> int:
    return int(time.time())


def _update_cast_state(**updates) -> None:
    with CAST_LOCK:
        CAST_STATE.update(updates)


def _load_floorplan_map() -> dict:
    if not FLOORPLAN_MAP_PATH.exists():
        return {'ambientes': {}, 'dispositivos': {}}

    try:
        data = yaml.safe_load(FLOORPLAN_MAP_PATH.read_text(encoding='utf-8')) or {}
    except Exception:
        return {'ambientes': {}, 'dispositivos': {}}

    return {
        'ambientes': data.get('ambientes', {}) or {},
        'dispositivos': data.get('dispositivos', {}) or {},
    }


FLOORPLAN_MAP = _load_floorplan_map()
FLOORPLAN_ENTITY_IDS = [
    config['helper_entity_id']
    for config in FLOORPLAN_MAP['ambientes'].values()
    if config.get('helper_entity_id')
] + [
    config['entity_id']
    for config in FLOORPLAN_MAP['dispositivos'].values()
    if config.get('entity_id')
]


def _load_host_network_state() -> dict:
    if not HOST_NETWORK_STATE_PATH.exists():
        return {}

    try:
        data = json.loads(HOST_NETWORK_STATE_PATH.read_text(encoding='utf-8-sig')) or {}
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _rewrite_url_host(url: str, host: str, *, default_port: int = 8090, default_path: str = '/') -> str:
    parsed = urlsplit(url)
    scheme = parsed.scheme or 'http'
    port = parsed.port or default_port
    path = parsed.path or default_path
    rebuilt = f'{scheme}://{host}:{port}{path}'
    if parsed.query:
        rebuilt = f'{rebuilt}?{parsed.query}'
    return rebuilt


def _current_public_url() -> str:
    selected_ip = str(_load_host_network_state().get('selected_ip', '')).strip()
    if selected_ip:
        return _rewrite_url_host(PUBLIC_URL, selected_ip, default_path='/')
    return PUBLIC_URL


def _default_snapshot_base_url() -> str:
    selected_ip = str(_load_host_network_state().get('selected_ip', '')).strip()
    if selected_ip and SNAPSHOT_BASE_URL:
        return _rewrite_url_host(SNAPSHOT_BASE_URL, selected_ip, default_path='/snapshots')

    if SNAPSHOT_BASE_URL:
        return SNAPSHOT_BASE_URL

    parsed = urlsplit(_current_public_url())
    if parsed.scheme and parsed.hostname:
        return f'{parsed.scheme}://{parsed.hostname}:{parsed.port or 8090}/snapshots'

    return ''


def _read_file_data_url(path: Path, mime_type: str) -> str:
    if not path.exists():
        return ''

    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'data:{mime_type};base64,{encoded}'


def _read_text_file(path: Path) -> str:
    if not path.exists():
        return ''

    return path.read_text(encoding='utf-8')


def _floorplan_svg_markup() -> str:
    svg = _read_text_file(FLOORPLAN_SVG_PATH)
    if not svg:
        return ''

    if svg.startswith('<?xml') and '?>' in svg:
        svg = svg.split('?>', 1)[1]

    return svg.replace('<!-- Created with Inkscape (http://www.inkscape.org/) -->', '', 1).strip()


def _floorplan_css_text() -> str:
    return _read_text_file(FLOORPLAN_CSS_PATH)



def _room_state_class(state: str | None) -> str:
    normalized = str(state or '').strip().lower()
    if not normalized or normalized in {'unavailable', 'unknown', 'offline'}:
        return 'room-unavailable'
    return 'room-helper-on' if normalized == 'on' else 'room-helper-off'


def _device_state_class(entity_id: str, state: str | None) -> str:
    normalized = str(state or '').strip().lower()
    if not normalized or normalized in UNAVAILABLE_STATES:
        return 'device-unavailable'

    domain = entity_id.split('.', 1)[0].lower()
    if domain == 'camera':
        return 'device-off' if normalized == 'off' else 'device-on'
    if domain == 'media_player':
        return 'device-off' if normalized in {'off', 'standby'} else 'device-on'
    if domain == 'climate':
        return 'device-off' if normalized == 'off' else 'device-on'
    if domain == 'input_select':
        if normalized == 'off':
            return 'device-off'
        return 'device-on'
    if normalized in DEVICE_ON_STATES:
        return 'device-on'
    if normalized in DEVICE_OFF_STATES:
        return 'device-off'
    return 'device-off'



def _load_auth_storage() -> dict:
    if not HA_AUTH_PATH.exists():
        return {}

    try:
        return json.loads(HA_AUTH_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _select_refresh_token() -> dict | None:
    tokens = _load_auth_storage().get('data', {}).get('refresh_tokens', [])
    normal_tokens = [
        token
        for token in tokens
        if token.get('token_type') == 'normal' and token.get('token') and token.get('client_id')
    ]
    normal_tokens.sort(key=lambda item: item.get('last_used_at') or item.get('created_at') or '', reverse=True)
    if normal_tokens:
        return normal_tokens[0]

    system_tokens = [token for token in tokens if token.get('token_type') == 'system' and token.get('token')]
    system_tokens.sort(key=lambda item: item.get('created_at') or '', reverse=True)
    if system_tokens:
        token = system_tokens[0].copy()
        token['client_id'] = token.get('client_id') or f'{HOME_ASSISTANT_URL}/'
        return token

    return None


def _get_ha_access_token(*, force_refresh: bool = False) -> str | None:
    now = time.time()
    with HA_TOKEN_LOCK:
        cached_token = HA_TOKEN_CACHE.get('access_token')
        if cached_token and not force_refresh and HA_TOKEN_CACHE.get('expires_at', 0.0) > now + 60:
            return cached_token

        refresh_token = _select_refresh_token()
        if not refresh_token:
            return None

        body = urlencode({
            'grant_type': 'refresh_token',
            'client_id': refresh_token['client_id'],
            'refresh_token': refresh_token['token'],
        }).encode('utf-8')
        request = Request(f'{HOME_ASSISTANT_URL}/auth/token', data=body, method='POST')
        request.add_header('Content-Type', 'application/x-www-form-urlencoded')

        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (HTTPError, URLError, TimeoutError, ValueError):
            return None

        access_token = payload.get('access_token')
        expires_in = float(payload.get('expires_in', 0) or 0)
        if not access_token:
            return None

        HA_TOKEN_CACHE['access_token'] = access_token
        HA_TOKEN_CACHE['expires_at'] = now + max(60.0, expires_in)
        return access_token


def _get_live_states_from_home_assistant(entity_ids: list[str]) -> dict[str, str]:
    if not entity_ids or not HOME_ASSISTANT_URL:
        return {}

    entity_set = set(entity_ids)
    access_token = _get_ha_access_token()
    if not access_token:
        return {}

    for attempt in range(2):
        request = Request(f'{HOME_ASSISTANT_URL}/api/states')
        request.add_header('Authorization', f'Bearer {access_token}')

        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode('utf-8'))
            break
        except HTTPError as exc:
            if exc.code == 401 and attempt == 0:
                access_token = _get_ha_access_token(force_refresh=True)
                if access_token:
                    continue
            return {}
        except (URLError, TimeoutError, ValueError):
            return {}
    else:
        return {}

    states = {}
    for item in payload:
        entity_id = item.get('entity_id')
        if entity_id in entity_set:
            states[entity_id] = item.get('state')

    return states


def _get_latest_states_from_db(entity_ids: list[str]) -> dict[str, str]:
    if not entity_ids or not HA_DB_PATH.exists():
        return {}

    placeholders = ', '.join('?' for _ in entity_ids)
    sql = f'''
        SELECT sm.entity_id, s.state
        FROM states s
        JOIN states_meta sm ON sm.metadata_id = s.metadata_id
        WHERE s.state_id IN (
            SELECT MAX(s2.state_id)
            FROM states s2
            JOIN states_meta sm2 ON sm2.metadata_id = s2.metadata_id
            WHERE sm2.entity_id IN ({placeholders})
            GROUP BY s2.metadata_id
        )
    '''
    connection_attempts = [
        (f'file:{HA_DB_PATH.as_posix()}?immutable=1', {'uri': True, 'timeout': 1.0}),
        (f'file:{HA_DB_PATH.as_posix()}?mode=ro', {'uri': True, 'timeout': 1.0}),
        (str(HA_DB_PATH), {'timeout': 1.0}),
    ]

    rows = None
    for target, kwargs in connection_attempts:
        try:
            with sqlite3.connect(target, **kwargs) as conn:
                conn.execute('PRAGMA query_only = ON')
                rows = conn.execute(sql, entity_ids).fetchall()
            break
        except sqlite3.Error:
            continue

    if rows is None:
        return {}

    return {entity_id: state for entity_id, state in rows}


def _get_latest_states(entity_ids: list[str]) -> dict[str, str]:
    live_states = _get_live_states_from_home_assistant(entity_ids)
    if len(live_states) == len(entity_ids):
        return live_states

    missing_entity_ids = [entity_id for entity_id in entity_ids if entity_id not in live_states]
    if not missing_entity_ids:
        return live_states

    db_states = _get_latest_states_from_db(missing_entity_ids)
    live_states.update(db_states)
    return live_states


def _build_floorplan_state_payload() -> dict:
    states = _get_latest_states(FLOORPLAN_ENTITY_IDS)
    elements = {}
    light_on_area_ids = set()

    for element_id, config in FLOORPLAN_MAP['dispositivos'].items():
        entity_id = config.get('entity_id')
        if not entity_id:
            continue

        device_class = _device_state_class(entity_id, states.get(entity_id))
        elements[element_id] = device_class
        area_id = str(config.get('area_id') or '').strip()
        visual_type = str(config.get('visual_type') or '').strip().lower()

        if visual_type == 'light':
            elements[f'glare.{element_id}'] = 'glare-on' if device_class == 'device-on' else ''
            if area_id and device_class == 'device-on':
                light_on_area_ids.add(area_id)

    for element_id, config in FLOORPLAN_MAP['ambientes'].items():
        area_id = str(config.get('area_id') or '').strip()
        if area_id and area_id in light_on_area_ids:
            elements[element_id] = 'room-light-on'
            continue

        entity_id = config.get('helper_entity_id')
        if entity_id:
            elements[element_id] = _room_state_class(states.get(entity_id))

    return {
        'ok': True,
        'elements': elements,
        'updated_at': int(time.time()),
    }

def _build_dashboard_html(
    *,
    rua_src: str,
    varanda_src: str,
    camera_base_url: str,
    floorplan_api_url: str,
    floorplan_event_url: str,
) -> str:
    floorplan_markup = _floorplan_svg_markup() or '<div class="empty-state">Planta indisponivel</div>'
    floorplan_css = _floorplan_css_text()
    dynamic_classes = ', '.join(f'"{name}"' for name in DYNAMIC_FLOORPLAN_CLASSES)
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{PAGE_REFRESH_SECONDS}">
  <title>Monitoramento</title>
  <style>
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      background: #000;
      color: #fff;
      font-family: Arial, sans-serif;
    }}
    .topbar {{
      padding: 12px 18px;
      background: #101820;
      font-size: 24px;
      font-weight: bold;
      letter-spacing: 1px;
    }}
    .subtitle {{
      float: right;
      font-size: 14px;
      font-weight: normal;
      color: #8fdcff;
      margin-top: 6px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.85fr);
      gap: 16px;
      height: calc(100vh - 76px);
      padding: 16px;
    }}
    .panel {{
      border: 2px solid #1d2f3d;
      background: #05080c;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .panel-title {{
      padding: 10px 12px;
      font-size: 22px;
      background: #162635;
    }}
    .panel-body {{
      flex: 1;
      min-height: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .floorplan-body {{
      padding: 8px;
      background: #f7f2e7;
    }}
    .floorplan-shell {{
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    .floorplan-shell svg {{
      width: 100%;
      height: 100%;
      max-width: 100%;
      max-height: 100%;
    }}
    .camera-column {{
      display: grid;
      grid-template-rows: 1fr 1fr;
      gap: 16px;
      min-height: 0;
    }}
    .camera-image {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #000;
    }}
    .empty-state {{
      width: 100%;
      padding: 24px;
      text-align: center;
      color: #c6d5df;
      font-size: 22px;
    }}
    {floorplan_css}
  </style>
</head>
<body>
  <div class="topbar">
    Planta + Cameras
    <span class="subtitle">Planta ao vivo | Cameras a cada {IMAGE_REFRESH_SECONDS}s</span>
  </div>
  <div class="layout">
    <div class="panel">
      <div class="panel-title">Planta</div>
      <div class="panel-body floorplan-body">
        <div class="floorplan-shell" id="floorplan-shell">
          {floorplan_markup}
        </div>
      </div>
    </div>
    <div class="camera-column">
      <div class="panel">
        <div class="panel-title">Rua</div>
        <div class="panel-body">
          <img class="camera-image" id="img_rua" src="{rua_src}" alt="Rua">
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">Varanda</div>
        <div class="panel-body">
          <img class="camera-image" id="img_varanda" src="{varanda_src}" alt="Varanda">
        </div>
      </div>
    </div>
  </div>
  <script type="text/javascript">
    var cameraBaseUrl = '{camera_base_url}';
    var floorplanApiUrl = '{floorplan_api_url}';
    var floorplanEventUrl = '{floorplan_event_url}';
    var dynamicClasses = [{dynamic_classes}];
    var floorplanPollTimer = null;
    var floorplanEventSource = null;

    function refreshImages() {{
      if (!cameraBaseUrl) {{
        return;
      }}
      var now = new Date().getTime();
      document.getElementById('img_rua').src = cameraBaseUrl + '/rua.jpg?t=' + now;
      document.getElementById('img_varanda').src = cameraBaseUrl + '/varanda.jpg?t=' + now;
    }}

    function applyFloorplanState(payload) {{
      if (!payload || !payload.elements) {{
        return;
      }}
      Object.entries(payload.elements).forEach(function(entry) {{
        var elementId = entry[0];
        var classNames = Array.isArray(entry[1]) ? entry[1] : (entry[1] ? [entry[1]] : []);
        var element = document.getElementById(elementId);
        if (!element) {{
          return;
        }}
        dynamicClasses.forEach(function(name) {{
          element.classList.remove(name);
        }});
        classNames.forEach(function(name) {{
          if (name) {{
            element.classList.add(name);
          }}
        }});
      }});
      var floorplanShell = document.getElementById('floorplan-shell');
      if (floorplanShell) {{
        floorplanShell.classList.add('floorplan-ready');
      }}
    }}

    async function refreshFloorplan() {{
      if (!floorplanApiUrl) {{
        return;
      }}
      try {{
        var response = await fetch(floorplanApiUrl + '?t=' + new Date().getTime(), {{ cache: 'no-store' }});
        if (!response.ok) {{
          return;
        }}
        applyFloorplanState(await response.json());
      }} catch (error) {{
      }}
    }}

    function stopFloorplanPolling() {{
      if (floorplanPollTimer) {{
        window.clearInterval(floorplanPollTimer);
        floorplanPollTimer = null;
      }}
    }}

    function ensureFloorplanPolling() {{
      if (floorplanPollTimer) {{
        return;
      }}
      refreshFloorplan();
      floorplanPollTimer = window.setInterval(refreshFloorplan, 2000);
    }}

    function connectFloorplanStream() {{
      if (!floorplanEventUrl || typeof EventSource === 'undefined') {{
        ensureFloorplanPolling();
        return;
      }}

      if (floorplanEventSource) {{
        return;
      }}

      try {{
        floorplanEventSource = new EventSource(floorplanEventUrl);
        floorplanEventSource.onmessage = function(event) {{
          if (!event.data) {{
            return;
          }}
          try {{
            applyFloorplanState(JSON.parse(event.data));
            stopFloorplanPolling();
          }} catch (error) {{
          }}
        }};
        floorplanEventSource.onerror = function() {{
          if (floorplanEventSource) {{
            floorplanEventSource.close();
            floorplanEventSource = null;
          }}
          ensureFloorplanPolling();
          window.setTimeout(connectFloorplanStream, 4000);
        }};
      }} catch (error) {{
        ensureFloorplanPolling();
      }}
    }}

    window.setTimeout(refreshImages, 900);
    window.setInterval(refreshImages, {IMAGE_REFRESH_SECONDS * 1000});
    window.setTimeout(connectFloorplanStream, 1200);
  </script>
</body>
</html>
'''


def _build_html(base_path: str, *, floorplan_api_url: str = '') -> str:
    now = int(time.time())
    return _build_dashboard_html(
        rua_src=f'{base_path}/rua.jpg?t={now}',
        varanda_src=f'{base_path}/varanda.jpg?t={now}',
        camera_base_url=base_path,
        floorplan_api_url=floorplan_api_url,
        floorplan_event_url='/api/floorplan/stream' if floorplan_api_url else '',
    )


def _build_embedded_html() -> str:
    snapshot_base_url = _default_snapshot_base_url()
    return _build_dashboard_html(
        rua_src=_read_file_data_url(CAMERAS['rua']['public_path'], 'image/jpeg') or './rua.jpg',
        varanda_src=_read_file_data_url(CAMERAS['varanda']['public_path'], 'image/jpeg') or './varanda.jpg',
        camera_base_url=snapshot_base_url,
        floorplan_api_url='',
        floorplan_event_url='',
    )




def _build_floorplan_signature(payload: dict) -> str:
    return json.dumps(payload.get('elements', {}), sort_keys=True, separators=(',', ':'))


def _floorplan_event_stream():
    last_signature = None
    last_heartbeat = 0.0

    while True:
        payload = _build_floorplan_state_payload()
        signature = _build_floorplan_signature(payload)
        now = time.monotonic()

        if signature != last_signature:
            last_signature = signature
            last_heartbeat = now
            yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
        elif now - last_heartbeat >= FLOORPLAN_STREAM_HEARTBEAT_SECONDS:
            last_heartbeat = now
            yield ': keep-alive\n\n'

        time.sleep(FLOORPLAN_WATCH_INTERVAL)


def _build_cast_url() -> str:
    if CAST_MODE == 'embedded':
        payload = base64.b64encode(_build_embedded_html().encode('utf-8')).decode('ascii')
        return f'data:text/html;charset=utf-8;base64,{payload}'

    return _current_public_url()


def _write_public_assets() -> None:
    (PUBLIC_DIR / 'index.html').write_text(_build_html('.', floorplan_api_url=''), encoding='utf-8')


def _capture_snapshot(name: str, camera: dict) -> None:
    temp_path = camera['snapshot_path'].with_suffix('.tmp.jpg')
    cmd = [
        'ffmpeg',
        '-loglevel',
        'error',
        '-rtsp_transport',
        'tcp',
        '-y',
        '-i',
        camera['rtsp_url'],
        '-vf',
        f'scale={SNAPSHOT_WIDTH}:-2',
        '-frames:v',
        '1',
        '-update',
        '1',
        '-q:v',
        '5',
        str(temp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip() or f'ffmpeg retornou {result.returncode}')

    data = temp_path.read_bytes()
    camera['snapshot_path'].write_bytes(data)
    camera['public_path'].write_bytes(data)
    temp_path.unlink(missing_ok=True)
    STATE[name]['ok'] = True
    STATE[name]['last_success'] = int(time.time())
    STATE[name]['last_error'] = None


def _snapshot_worker(name: str, camera: dict) -> None:
    while True:
        try:
            _capture_snapshot(name, camera)
        except Exception as exc:  # noqa: BLE001
            STATE[name]['ok'] = False
            STATE[name]['last_error'] = str(exc)
        time.sleep(SNAPSHOT_INTERVAL)


def _get_cast() -> pychromecast.Chromecast:
    kwargs = {}
    if CHROMECAST_KNOWN_HOSTS:
        kwargs['known_hosts'] = CHROMECAST_KNOWN_HOSTS

    casts, browser = pychromecast.get_chromecasts(**kwargs)
    try:
        if not casts:
            raise RuntimeError(
                f'Chromecast nao encontrado. Hosts configurados: {CHROMECAST_KNOWN_HOSTS or ["discovery"]}'
            )

        if CHROMECAST_NAME:
            for cast in casts:
                if cast.name.strip().casefold() == CHROMECAST_NAME.casefold():
                    cast.wait()
                    return cast

            available = [cast.name for cast in casts]
            raise RuntimeError(
                f'Chromecast "{CHROMECAST_NAME}" nao encontrado. Dispositivos vistos: {available}'
            )

        cast = casts[0]
        cast.wait()
        return cast
    finally:
        if browser is not None:
            pychromecast.discovery.stop_discovery(browser)


def _start_dashcast(*, quit_on_failure: bool = True) -> tuple[pychromecast.Chromecast, int, str]:
    last_error = None
    cast_url = _build_cast_url()

    for attempt in range(1, CAST_START_ATTEMPTS + 1):
        cast = _get_cast()
        controller = DashCastController()
        cast.register_handler(controller)

        try:
            time.sleep(CAST_READY_DELAY_SECONDS)
            controller.load_url(cast_url, force=True)
            return cast, attempt, cast_url
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if quit_on_failure:
                try:
                    cast.quit_app()
                except Exception:  # noqa: BLE001
                    pass

            if attempt == CAST_START_ATTEMPTS:
                break

            time.sleep(CAST_START_RETRY_SECONDS)

    raise RuntimeError(
        f'Nao foi possivel iniciar o DashCast apos {CAST_START_ATTEMPTS} tentativas: {last_error}'
    )


def _cast_status_value(status: object, field: str) -> str:
    return str(getattr(status, field, '') or '').strip()


def _inspect_cast_session(cast: pychromecast.Chromecast) -> dict:
    status = cast.status
    app_id = _cast_status_value(status, 'app_id')
    display_name = _cast_status_value(status, 'display_name')
    return {
        'device': cast.name,
        'app_id': app_id,
        'display_name': display_name,
        'session_id': _cast_status_value(status, 'session_id'),
        'is_dashcast': app_id in DASHCAST_APP_IDS or display_name.casefold() == 'dashcast',
    }


def _attempt_watchdog_recovery(reason: str) -> None:
    now = _now_ts()
    with CAST_LOCK:
        if not CAST_STATE['desired_active']:
            return

        last_recovery_attempt = CAST_STATE.get('last_recovery_attempt')
        if last_recovery_attempt and now - int(last_recovery_attempt) < CAST_WATCHDOG_RECOVERY_COOLDOWN:
            CAST_STATE['last_watchdog_status'] = 'cooldown'
            CAST_STATE['last_watchdog_reason'] = reason
            return

        CAST_STATE['last_recovery_attempt'] = now
        CAST_STATE['last_watchdog_status'] = 'recovering'
        CAST_STATE['last_watchdog_reason'] = reason
        APP.logger.warning('Watchdog tentando recuperar o cast: %s', reason)

        try:
            cast, attempt, _ = _start_dashcast()
            session = _inspect_cast_session(cast)
        except Exception as exc:  # noqa: BLE001
            CAST_STATE['active'] = False
            CAST_STATE['last_error'] = f'{reason}; recovery failed: {exc}'
            CAST_STATE['last_watchdog_status'] = 'recovery-failed'
            CAST_STATE['recovery_failures'] = int(CAST_STATE.get('recovery_failures') or 0) + 1
            APP.logger.error('Watchdog falhou ao recuperar o cast: %s', CAST_STATE['last_error'])
            return

        CAST_STATE['active'] = True
        CAST_STATE['last_start'] = now
        CAST_STATE['last_refresh'] = now
        CAST_STATE['last_error'] = None
        CAST_STATE['last_watchdog_status'] = 'recovered'
        CAST_STATE['last_watchdog_reason'] = reason
        CAST_STATE['last_recovery_success'] = now
        CAST_STATE['last_watchdog_check'] = now
        CAST_STATE['recovery_count'] = int(CAST_STATE.get('recovery_count') or 0) + 1
        CAST_STATE['last_seen_device'] = session['device']
        CAST_STATE['last_seen_app_id'] = PRIMARY_DASHCAST_APP_ID
        CAST_STATE['last_seen_display_name'] = 'DashCast'

    APP.logger.warning(
        'Watchdog recuperou o cast no dispositivo %s apos %s tentativas internas do DashCast.',
        cast.name,
        attempt,
    )


def _cast_watchdog_worker() -> None:
    APP.logger.warning(
        'Cast watchdog habilitado. Intervalo=%ss cooldown=%ss grace=%ss',
        CAST_WATCHDOG_INTERVAL,
        CAST_WATCHDOG_RECOVERY_COOLDOWN,
        CAST_WATCHDOG_START_GRACE_SECONDS,
    )

    while True:
        time.sleep(CAST_WATCHDOG_INTERVAL)
        now = _now_ts()

        if not CAST_STATE.get('desired_active'):
            _update_cast_state(
                last_watchdog_check=now,
                last_watchdog_status='idle',
                last_watchdog_reason=None,
            )
            continue

        last_start = CAST_STATE.get('last_start')
        if last_start and now - int(last_start) < CAST_WATCHDOG_START_GRACE_SECONDS:
            _update_cast_state(
                last_watchdog_check=now,
                last_watchdog_status='start-grace',
                last_watchdog_reason=None,
            )
            continue

        try:
            cast = _get_cast()
            session = _inspect_cast_session(cast)
        except Exception as exc:  # noqa: BLE001
            reason = f'watchdog nao conseguiu consultar o Chromecast: {exc}'
            _update_cast_state(
                active=False,
                last_error=reason,
                last_watchdog_check=now,
                last_watchdog_status='chromecast-unreachable',
                last_watchdog_reason=reason,
            )
            APP.logger.error(reason)
            _attempt_watchdog_recovery(reason)
            continue

        _update_cast_state(
            last_watchdog_check=now,
            last_seen_device=session['device'],
            last_seen_app_id=session['app_id'],
            last_seen_display_name=session['display_name'],
        )

        if session['is_dashcast']:
            _update_cast_state(
                active=True,
                last_refresh=now,
                last_error=None,
                last_watchdog_status='ok',
                last_watchdog_reason=None,
            )
            continue

        app_label = session['display_name'] or session['app_id'] or 'desconhecido'
        reason = f'watchdog detectou sessao inesperada no Chromecast: {app_label}'
        _update_cast_state(
            active=False,
            last_error=reason,
            last_watchdog_status='session-lost',
            last_watchdog_reason=reason,
        )
        APP.logger.warning(reason)
        _attempt_watchdog_recovery(reason)


@APP.get('/')
def index() -> Response:
    response = make_response(_build_html('/snapshots', floorplan_api_url='/api/floorplan/state'))
    response.mimetype = 'text/html'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@APP.get('/health')
def health() -> Response:
    host_network_state = _load_host_network_state()
    return jsonify(
        {
            'ok': True,
            'cameras': STATE,
            'public_url': _current_public_url(),
            'configured_public_url': PUBLIC_URL,
            'snapshot_base_url': _default_snapshot_base_url(),
            'home_assistant_url': HOME_ASSISTANT_URL,
            'cast_mode': CAST_MODE,
            'chromecast_ip': ','.join(CHROMECAST_KNOWN_HOSTS),
            'chromecast_known_hosts': CHROMECAST_KNOWN_HOSTS,
            'chromecast_name': CHROMECAST_NAME,
            'host_network_state_path': str(HOST_NETWORK_STATE_PATH),
            'host_network_state': host_network_state,
            'image_refresh_seconds': IMAGE_REFRESH_SECONDS,
            'floorplan_watch_interval': FLOORPLAN_WATCH_INTERVAL,
            'floorplan_stream_heartbeat_seconds': FLOORPLAN_STREAM_HEARTBEAT_SECONDS,
            'snapshot_width': SNAPSHOT_WIDTH,
            'public_dir': str(PUBLIC_DIR),
            'ha_config_dir': str(HA_CONFIG_DIR),
            'floorplan_svg_path': str(FLOORPLAN_SVG_PATH),
            'floorplan_map_path': str(FLOORPLAN_MAP_PATH),
            'floorplan_element_count': len(FLOORPLAN_MAP['ambientes']) + len(FLOORPLAN_MAP['dispositivos']),
            'cast_watchdog': {
                'enabled': CAST_WATCHDOG_ENABLED,
                'interval_seconds': CAST_WATCHDOG_INTERVAL,
                'recovery_cooldown_seconds': CAST_WATCHDOG_RECOVERY_COOLDOWN,
                'start_grace_seconds': CAST_WATCHDOG_START_GRACE_SECONDS,
                'dashcast_app_ids': sorted(DASHCAST_APP_IDS),
            },
            'cast': CAST_STATE,
        }
    )


@APP.get('/api/floorplan/state')
def floorplan_state() -> Response:
    response = make_response(jsonify(_build_floorplan_state_payload()))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@APP.get('/api/floorplan/stream')
def floorplan_stream() -> Response:
    response = Response(_floorplan_event_stream(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@APP.get('/snapshots/<camera_name>.jpg')
def snapshot(camera_name: str):
    camera = CAMERAS.get(camera_name)
    if camera is None:
        return jsonify({'error': 'camera nao encontrada'}), 404

    path = camera['snapshot_path']
    if not path.exists():
        return jsonify({'error': 'snapshot indisponivel', 'details': STATE[camera_name]}), 503

    response = make_response(send_file(path, mimetype='image/jpeg', max_age=0, conditional=False))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@APP.post('/api/cast/start')
def cast_start() -> Response:
    with CAST_LOCK:
        cast, attempt, cast_url = _start_dashcast()
        session = _inspect_cast_session(cast)
        CAST_STATE['active'] = True
        CAST_STATE['desired_active'] = True
        CAST_STATE['last_start'] = _now_ts()
        CAST_STATE['last_refresh'] = CAST_STATE['last_start']
        CAST_STATE['last_error'] = None
        CAST_STATE['last_watchdog_status'] = 'started'
        CAST_STATE['last_watchdog_reason'] = None
        CAST_STATE['last_seen_device'] = session['device']
        CAST_STATE['last_seen_app_id'] = PRIMARY_DASHCAST_APP_ID
        CAST_STATE['last_seen_display_name'] = 'DashCast'

    return jsonify(
        {
            'ok': True,
            'action': 'start',
            'url': 'embedded:data-url' if CAST_MODE == 'embedded' else cast_url,
            'device': cast.name,
            'force': True,
            'attempt': attempt,
            'cast_mode': CAST_MODE,
        }
    )


@APP.post('/api/cast/stop')
def cast_stop() -> Response:
    with CAST_LOCK:
        CAST_STATE['desired_active'] = False
        CAST_STATE['active'] = False
        CAST_STATE['last_watchdog_status'] = 'stopped'
        CAST_STATE['last_watchdog_reason'] = None
        CAST_STATE['last_error'] = None
        device_name = CHROMECAST_NAME or 'chromecast'

        try:
            cast = _get_cast()
            cast.quit_app()
            device_name = cast.name
        except Exception as exc:  # noqa: BLE001
            warning = f'cast parado localmente, mas nao foi possivel encerrar app remoto: {exc}'
            CAST_STATE['last_error'] = warning
            APP.logger.warning(warning)
            return jsonify({'ok': True, 'action': 'stop', 'device': device_name, 'details': warning})

    return jsonify({'ok': True, 'action': 'stop', 'device': device_name})


_write_public_assets()
for camera_name, camera_config in CAMERAS.items():
    thread = threading.Thread(target=_snapshot_worker, args=(camera_name, camera_config), daemon=True)
    thread.start()

if CAST_WATCHDOG_ENABLED:
    watchdog_thread = threading.Thread(target=_cast_watchdog_worker, name='cast-watchdog', daemon=True)
    watchdog_thread.start()


if __name__ == '__main__':
    APP.run(host='0.0.0.0', port=8090, threaded=True)






