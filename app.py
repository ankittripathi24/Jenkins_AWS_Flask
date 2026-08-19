from flask import Flask, Blueprint, render_template, request, jsonify, send_from_directory, g
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import requests
import json
import logging
import sys
import base64
import threading
import time
app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger('flaskapp')
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    logger.addHandler(handler)
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
# ── Configuration (all from environment variables) ───────────────────────────
# Set these before running:
#   export IH_APP_CLIENT_ID="your-client-id"
#   export IH_APP_CLIENT_SECRET="your-client-secret"
#   export IH_APP_NAME="flaskapp"
#   export IH_APP_VERSION="v1.0.1"
#   export IH_HOST_TENANT="tppnr04"
#   export BASE_PATH=""          # e.g. "/tppnr04-flaskapp-tppnr04" on MindSphere / Render
#   export LOG_LEVEL="INFO"
#   export PORT="5000"
MINDSPHERE_API_BASE   = os.environ.get('MINDSPHERE_API_BASE',   'https://gateway.eu1.mindsphere.io')
IH_APP_CLIENT_ID      = os.environ.get('IH_APP_CLIENT_ID',      '')
IH_APP_CLIENT_SECRET  = os.environ.get('IH_APP_CLIENT_SECRET',  '')
IH_APP_NAME           = os.environ.get('IH_APP_NAME',           'flaskapp')
IH_APP_VERSION        = os.environ.get('IH_APP_VERSION',        'v1.0.1')
IH_HOST_TENANT        = os.environ.get('IH_HOST_TENANT',        '')
# BASE_PATH must start with "/" if set, e.g. "/tppnd04-renderingflask-tppnd04"
# Leave empty ("") for AWS / local — routes will be registered at "/"
BASE_PATH             = os.environ.get('BASE_PATH', '').rstrip('/')
# ── Token cache ───────────────────────────────────────────────────────────────
_token_lock  = threading.Lock()
_token_cache: dict = {}   # { user_tenant: { token: str, expires_at: float } }
# ── In-memory submissions store ───────────────────────────────────────────────
submissions = []
logger.info(
    'App starting | BASE_PATH=%s | API_BASE=%s | LOG_LEVEL=%s | host_tenant=%s | credentials_configured=%s',
    BASE_PATH, MINDSPHERE_API_BASE, LOG_LEVEL, IH_HOST_TENANT,
    bool(IH_APP_CLIENT_ID and IH_APP_CLIENT_SECRET)
)
# ── Helpers ───────────────────────────────────────────────────────────────────
def mask_secret(value, visible_prefix=10, visible_suffix=10):
    """Mask a sensitive string for safe logging."""
    if not value:
        return '***'
    if len(value) <= (visible_prefix + visible_suffix):
        return '***'
    return f'{value[:visible_prefix]}...{value[-visible_suffix:]}'
def build_api_url(service_path: str) -> str:
    """Build a full IH API URL from a relative service path.
    Example:
        build_api_url('assetmanagement/v3/assets')
        → 'https://gateway.eu1.mindsphere.io/api/assetmanagement/v3/assets'
    """
    return f'{MINDSPHERE_API_BASE}/api/{service_path}'
class CredentialsMissingError(Exception):
    """Raised when IH_APP_CLIENT_ID or IH_APP_CLIENT_SECRET are not set."""
def _fetch_app_token(user_tenant: str):
    """Request a fresh Bearer token from the Technical Token Manager."""
    if not IH_APP_CLIENT_ID or not IH_APP_CLIENT_SECRET:
        raise CredentialsMissingError(
            'App credentials not configured. '
            'Set IH_APP_CLIENT_ID and IH_APP_CLIENT_SECRET environment variables.'
        )
    b64 = base64.b64encode(f'{IH_APP_CLIENT_ID}:{IH_APP_CLIENT_SECRET}'.encode()).decode()
    url = f'{MINDSPHERE_API_BASE}/api/technicaltokenmanager/v3/oauth/token'
    payload = {
        'grant_type':  'client_credentials',
        'appName':     IH_APP_NAME,
        'appVersion':  IH_APP_VERSION,
        'hostTenant':  IH_HOST_TENANT,
        'userTenant':  user_tenant,
    }
    headers = {
        'x-space-auth-key': f'Bearer {b64}',
        'Content-Type':     'application/json',
    }
    logger.info(
        'Token request | url=%s | appName=%s | appVersion=%s | hostTenant=%s | userTenant=%s',
        url, IH_APP_NAME, IH_APP_VERSION, IH_HOST_TENANT, user_tenant
    )
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        logger.error('Token fetch failed | status=%s | body=%s', resp.status_code, resp.text[:300])
        resp.raise_for_status()
    data = resp.json()
    return data['access_token'], int(data.get('expires_in', 1800))
def get_app_token() -> str:
    """Return a valid cached token for the current request's tenant, refreshing when near expiry."""
    user_tenant = getattr(g, 'user_tenant', IH_HOST_TENANT)
    with _token_lock:
        entry = _token_cache.get(user_tenant)
        if entry and time.time() < entry['expires_at'] - 60:
            return entry['token']
        token, expires_in = _fetch_app_token(user_tenant)
        _token_cache[user_tenant] = {'token': token, 'expires_at': time.time() + expires_in}
        logger.info('Token refreshed | user_tenant=%s | expires_in=%ss', user_tenant, expires_in)
        return token
def ih_get(url: str, **kwargs):
    """Authenticated GET against the IH API. Retries once on 401 with a fresh token."""
    user_tenant = getattr(g, 'user_tenant', IH_HOST_TENANT)
    logger.info('ih_get | url=%s | params=%s | user_tenant=%s', url, kwargs.get('params', {}), user_tenant)
    token = get_app_token()
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    resp = requests.get(url, headers=headers, **kwargs)
    logger.info('ih_get response | status=%s | url=%s', resp.status_code, url)
    if resp.status_code == 401:
        logger.warning('Got 401 — refreshing token for tenant=%s and retrying | url=%s', user_tenant, url)
        with _token_lock:
            _token_cache.pop(user_tenant, None)
        token = get_app_token()
        headers['Authorization'] = f'Bearer {token}'
        resp = requests.get(url, headers=headers, **kwargs)
        logger.info('ih_get retry | status=%s | url=%s', resp.status_code, url)
    if resp.status_code not in (200, 201, 204):
        logger.warning('ih_get non-success | status=%s | body=%s', resp.status_code, resp.text[:300])
    return resp
# ── Request interceptor ───────────────────────────────────────────────────────
@app.before_request
def set_request_context():
    """Resolve user_tenant and base_path for every incoming request."""
    # Tenant: prefer the gateway-injected header, fall back to host tenant
    ms_tenant_header = request.headers.get('X-MindSphere-Tenant')
    forwarded_host   = request.headers.get('X-Forwarded-Host', '')
    subdomain        = forwarded_host.split('.')[0] if forwarded_host else ''
    app_separator    = f'-{IH_APP_NAME}-'
    if ms_tenant_header:
        g.user_tenant = ms_tenant_header
    elif app_separator in subdomain:
        # e.g. "callerTenant-flaskapp-hostTenant" → "callerTenant"
        g.user_tenant = subdomain.split(app_separator)[0]
    else:
        g.user_tenant = IH_HOST_TENANT
    # Base path: derive from X-Forwarded-Host when deployed, use env var locally
    if forwarded_host:
        g.base_path = f'/{subdomain}'
    else:
        g.base_path = BASE_PATH
    logger.info(
        'Request | method=%s | path=%s | user_tenant=%s | base_path=%s | remote_ip=%s',
        request.method, request.path, g.user_tenant, g.base_path, request.remote_addr
    )
    # Skip verbose header logging for ELB health checks
    if 'ELB-HealthChecker' in request.headers.get('User-Agent', ''):
        return
    for header, value in request.headers:
        if header.lower() in ('authorization', 'cookie', 'x-xsrf-token'):
            logger.debug('Header %s=***masked***', header)
        else:
            logger.debug('Header %s=%s', header, value)
# ── Blueprint ─────────────────────────────────────────────────────────────────
# All routes are defined on this blueprint.
#
# When BASE_PATH is set  (Render / MindSphere):
#   url_prefix="/tppnd04-renderingflask-tppnd04"
#   → Flask matches /tppnd04-renderingflask-tppnd04/api/...
#
# When BASE_PATH is empty (AWS / local):
#   url_prefix=""
#   → Flask matches /api/...  (no change from original behaviour)
#
# No duplicate @app.route decorators needed — one definition covers all envs.
bp = Blueprint('main', __name__)
# ── Page routes ───────────────────────────────────────────────────────────────
@bp.route('/')
def index():
    try:
        return render_template('dashboard.html', base_path=BASE_PATH)
    except Exception as e:
        logger.exception('Failed to render dashboard: %s', e)
        # Return the real error detail so it's visible during debugging
        import traceback
        return jsonify({
            'error': 'Failed to render page',
            'detail': str(e),
            'traceback': traceback.format_exc()
        }), 500
@bp.route('/app-info.json')
def app_info():
    try:
        return send_from_directory(app.static_folder, 'app-info.json')
    except Exception as e:
        logger.exception('Failed to serve app-info.json: %s', e)
        return jsonify({'error': 'File not found'}), 404
@bp.route('/text-submission')
def text_submission():
    try:
        return render_template('index.html', base_path=BASE_PATH)
    except Exception as e:
        logger.exception('Failed to render text submission page: %s', e)
        return jsonify({'error': 'Failed to render page'}), 500
# ── Submission API ────────────────────────────────────────────────────────────
@bp.route('/api/submit', methods=['POST'])
def submit_text():
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'text' not in data:
            return jsonify({'success': False, 'error': 'Missing required fields: name and text'}), 400
        submission = {
            'id':        len(submissions) + 1,
            'name':      data['name'],
            'text':      data['text'],
            'timestamp': datetime.now().isoformat()
        }
        submissions.append(submission)
        logger.info('Submission stored | id=%s | total=%s', submission['id'], len(submissions))
        return jsonify({'success': True, 'message': 'Text submitted successfully', 'submission': submission}), 201
    except Exception as e:
        logger.exception('Submit endpoint failed: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
@bp.route('/api/submissions', methods=['GET'])
def get_submissions():
    return jsonify({'success': True, 'count': len(submissions), 'submissions': submissions}), 200
@bp.route('/api/submissions/<int:submission_id>', methods=['GET'])
def get_submission(submission_id):
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    if submission:
        return jsonify({'success': True, 'submission': submission}), 200
    return jsonify({'success': False, 'error': 'Submission not found'}), 404
# ── Insights Hub API routes ───────────────────────────────────────────────────
@bp.route('/api/insights-hub/dashboard-metrics', methods=['GET'])
def get_dashboard_metrics():
    """Call 10 IH APIs and return counts for the dashboard."""
    metrics = {}
    errors  = []
    # Each entry: (metrics_key, service_path, params)
    api_calls = [
        ('assets',             'assetmanagement/v3/assets',              {'size': 1}),
        ('agents',             'assetmanagement/v3/assets',              {'filter': '{"hasType":{"in":["core.basicagent"]}}', 'size': 1}),
        ('vfc_flows',          'visualflowcreator/v3/flows',             {'size': 1}),
        ('dashboards',         'kpidashboardconfiguration/v3/dashboards', {'size': 1}),
        ('rules',              'rulesmanagement/v4/rules',               {'size': 1}),
        ('cases',              'casemanagement/v3/cases',                {'size': 1}),
        ('predictions',        'oipredictapi/v3/predict-assets/all',     {}),
        ('anomaly_detections', 'oipredictapi/v3/usageDetails',           {'requestType': 'ANOMALY'}),
    ]
    # Events needs a dynamic timestamp — handle separately
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    api_calls.append((
        'events',
        'eventmanagement/v3/events',
        {'size': 1, 'filter': f'{{"timestamp":{{"after":"{one_year_ago}"}}}}', 'history': 'true', 'includeShared': 'false'}
    ))
    # Data lake is also slightly different (different response shape) — handle separately
    try:
        resp = ih_get(build_api_url('datalake/v3/listObjects'), params={'path': '/', 'size': 1000}, timeout=30)
        if resp.status_code == 200:
            objs = resp.json().get('objects', {})
            metrics['datalake'] = {'objects': len(objs.get('files', [])) + len(objs.get('folders', [])), 'status': 'success'}
        else:
            metrics['datalake'] = {'objects': 0, 'status': 'error', 'message': f'HTTP {resp.status_code}'}
            errors.append(f'datalake → HTTP {resp.status_code}')
    except Exception as e:
        metrics['datalake'] = {'objects': 0, 'status': 'error', 'message': str(e)}
        errors.append(f'datalake → {e}')
    # All other APIs share the same response shape: page.totalElements
    for key, service_path, params in api_calls:
        try:
            resp = ih_get(build_api_url(service_path), params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                # cases uses top-level totalElements; everything else nests under page
                count = data.get('page', data).get('totalElements', 0)
                metrics[key] = {'count': count, 'status': 'success'}
                logger.info('%s count=%s', key, count)
            else:
                metrics[key] = {'count': 0, 'status': 'error', 'message': f'HTTP {resp.status_code}'}
                errors.append(f'{key} → HTTP {resp.status_code}')
        except Exception as e:
            logger.exception('%s API call failed: %s', key, e)
            metrics[key] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'{key} → {e}')
    return jsonify({
        'success':   True,
        'metrics':   metrics,
        'errors':    errors or None,
        'timestamp': datetime.now().isoformat()
    }), 200
@bp.route('/api/insights-hub/assets', methods=['GET'])
def get_insights_hub_assets():
    """Proxy the IH Asset Management API."""
    try:
        params = {'size': request.args.get('size', 10), 'page': request.args.get('page', 0)}
        if request.args.get('filter'):
            params['filter'] = request.args.get('filter')
        resp = ih_get(build_api_url('assetmanagement/v3/assets'), params=params, timeout=30)
        if resp.status_code == 200:
            return jsonify({'success': True, 'data': resp.json()}), 200
        return jsonify({'success': False, 'error': f'IH API error: {resp.status_code}', 'details': resp.text}), resp.status_code
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Request to Insights Hub timed out'}), 504
    except Exception as e:
        logger.exception('Assets proxy failed: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
@bp.route('/api/insights-hub/tenant-info', methods=['GET'])
def get_tenant_info():
    return jsonify({
        'success':                True,
        'tenant':                 getattr(g, 'user_tenant', IH_HOST_TENANT),
        'host_tenant':            IH_HOST_TENANT,
        'app_name':               IH_APP_NAME,
        'app_version':            IH_APP_VERSION,
        'api_base':               MINDSPHERE_API_BASE,
        'credentials_configured': bool(IH_APP_CLIENT_ID and IH_APP_CLIENT_SECRET),
        'timestamp':              datetime.now().isoformat()
    }), 200
@bp.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200
# ── Register Blueprint ────────────────────────────────────────────────────────
# BASE_PATH=""  → prefix=""  → routes at /api/...                    (AWS / local)
# BASE_PATH="/tppnd04-renderingflask-tppnd04"
#             → routes at /tppnd04-renderingflask-tppnd04/api/...    (Render / MindSphere)
app.register_blueprint(bp, url_prefix=BASE_PATH)
# ── Root redirect (Render / MindSphere only) ───────────────────────────────
# When BASE_PATH is set, MindSphere / Render may hit bare "/" before the OS Bar
# rewrites the path. Redirect it to the real prefixed index so the UI always loads.
if BASE_PATH:
    @app.route('/')
    def _root_index():
        # MindSphere hits bare "/" — serve the app directly (no redirect).
        # A 302 redirect is not followed by the MindSphere app loader.
        try:
            return render_template('dashboard.html', base_path=BASE_PATH)
        except Exception as e:
            logger.exception('Failed to render dashboard at root: %s', e)
            import traceback
            return jsonify({'error': 'Failed to render page', 'detail': str(e),
                            'traceback': traceback.format_exc()}), 500
# ── MindSphere OS Bar API proxy ───────────────────────────────────────────────
# The MindSphere OS Bar (main.min.js) makes calls to platform APIs like
# /api/tenantmanagement/..., /api/im/..., /api/userprofilemanagement/...
# These arrive at our Flask app without the BASE_PATH prefix.
# We forward them transparently to the MindSphere gateway so the OS Bar works.
#
# NOTE: This proxy only handles GET requests made by the OS Bar.
# It is NOT used for our own IH API calls (those use ih_get() directly).
OS_BAR_API_PREFIXES = (
    '/api/tenantmanagement/',
    '/api/im/',
    '/api/userprofilemanagement/',
    '/api/pushnotification/',
    '/api/customers/',
)
@app.route('/api/<path:api_path>', methods=['GET'])
def osbar_api_proxy(api_path):
    """Forward OS Bar platform API calls to the MindSphere gateway."""
    full_path = '/api/' + api_path
    # Only proxy known OS Bar prefixes — don't intercept our own /api/insights-hub/ routes
    # (those are handled by the blueprint and will never reach this catch-all)
    if not any(full_path.startswith(p) for p in OS_BAR_API_PREFIXES):
        return jsonify({'error': 'Not found', 'path': full_path}), 404
    target_url = MINDSPHERE_API_BASE + full_path
    query_string = request.query_string.decode('utf-8')
    if query_string:
        target_url += '?' + query_string
    logger.info('OS Bar proxy | path=%s | target=%s', full_path, target_url)
    try:
        token = get_app_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        resp = requests.get(target_url, headers=headers, timeout=15)
        logger.info('OS Bar proxy response | status=%s | path=%s', resp.status_code, full_path)
        # Forward the response as-is
        try:
            return jsonify(resp.json()), resp.status_code
        except Exception:
            return resp.text, resp.status_code, {'Content-Type': resp.headers.get('Content-Type', 'text/plain')}
    except Exception as e:
        logger.exception('OS Bar proxy failed | path=%s | error=%s', full_path, e)
        return jsonify({'error': str(e)}), 502
# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(CredentialsMissingError)
def handle_credentials_missing(e):
    logger.error('Credentials missing: %s', e)
    return jsonify({
        'success': False,
        'error':   str(e),
        'hint':    'Set IH_APP_CLIENT_ID and IH_APP_CLIENT_SECRET as environment variables.'
    }), 503
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'path': request.path}), 404
@app.errorhandler(500)
def internal_error(error):
    logger.exception('Unhandled 500 | path=%s | error=%s', request.path, error)
    return jsonify({'error': 'Internal server error'}), 500
# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
