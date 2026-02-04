from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Support for base path (for Insights Hub/MindSphere deployment)
BASE_PATH = os.environ.get('BASE_PATH', '').rstrip('/')

# Insights Hub API base URL - Gateway endpoint
INSIGHTS_HUB_API_BASE = 'https://gateway.eu1.mindsphere.io'

# Store submissions in memory (in production, use a database)
submissions = []

@app.route(f'{BASE_PATH}/')
@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('dashboard.html', base_path=BASE_PATH)

@app.route(f'{BASE_PATH}/text-submission')
@app.route('/text-submission')
def text_submission():
    """Render the text submission page"""
    return render_template('index.html', base_path=BASE_PATH)

@app.route(f'{BASE_PATH}/api/submit', methods=['POST'])
@app.route('/api/submit', methods=['POST'])
def submit_text():
    """API endpoint to handle text submissions"""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'name' not in data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: name and text'
            }), 400
        
        # Create submission entry
        submission = {
            'id': len(submissions) + 1,
            'name': data['name'],
            'text': data['text'],
            'timestamp': datetime.now().isoformat()
        }
        
        submissions.append(submission)
        
        return jsonify({
            'success': True,
            'message': 'Text submitted successfully',
            'submission': submission
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route(f'{BASE_PATH}/api/submissions', methods=['GET'])
@app.route('/api/submissions', methods=['GET'])
def get_submissions():
    """API endpoint to retrieve all submissions"""
    return jsonify({
        'success': True,
        'count': len(submissions),
        'submissions': submissions
    }), 200

@app.route(f'{BASE_PATH}/api/submissions/<int:submission_id>', methods=['GET'])
@app.route('/api/submissions/<int:submission_id>', methods=['GET'])
def get_submission(submission_id):
    """API endpoint to retrieve a specific submission"""
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    
    if submission:
        return jsonify({
            'success': True,
            'submission': submission
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': 'Submission not found'
        }), 404

@app.route(f'{BASE_PATH}/api/insights-hub/dashboard-metrics', methods=['GET'])
@app.route('/api/insights-hub/dashboard-metrics', methods=['GET'])
def get_dashboard_metrics():
    """Fetch comprehensive metrics from Insights Hub tenant"""
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'No authorization token provided'
            }), 401
        
        headers = {
            'Authorization': auth_header,
            'Content-Type': 'application/json'
        }
        
        metrics = {}
        errors = []
        
        # 1. Get Asset Count
        try:
            assets_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets',
                headers=headers,
                params={'size': 1},
                timeout=30
            )
            if assets_response.status_code == 200:
                assets_data = assets_response.json()
                metrics['assets'] = {
                    'count': assets_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['assets'] = {'count': 0, 'status': 'error', 'message': f'HTTP {assets_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets → HTTP {assets_response.status_code}')
        except Exception as e:
            metrics['assets'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets → {str(e)}')
        
        # 2. Get Agent Count from Asset Manager
        try:
            agents_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets',
                headers=headers,
                params={'filter': '{"hasType":{"in":["core.basicagent"]}}', 'page': 1000000, 'size': 200},
                timeout=30
            )
            if agents_response.status_code == 200:
                agents_data = agents_response.json()
                metrics['agents'] = {
                    'count': agents_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['agents'] = {'count': 0, 'status': 'error', 'message': f'HTTP {agents_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets?filter={{"hasType":{{"in":["core.basicagent"]}}}} → HTTP {agents_response.status_code}')
        except Exception as e:
            metrics['agents'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets (agents filter) → {str(e)}')
        
        # 3. Get Data Lake Objects Count
        try:
            datalake_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/datalake/v3/listObjects',
                headers=headers,
                params={'path': '/', 'size': 1},
                timeout=30
            )
            if datalake_response.status_code == 200:
                datalake_data = datalake_response.json()
                total_objects = datalake_data.get('page', {}).get('totalElements', 0)
                # Try to get size info if available
                metrics['datalake'] = {
                    'objects': total_objects,
                    'status': 'success'
                }
            else:
                metrics['datalake'] = {'objects': 0, 'status': 'error', 'message': f'HTTP {datalake_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/datalake/v3/listObjects?path=/ → HTTP {datalake_response.status_code}')
        except Exception as e:
            metrics['datalake'] = {'objects': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/datalake/v3/listObjects?path=/ → {str(e)}')
        
        # 4. Get Event Count
        try:
            events_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/eventmanagement/v3/events',
                headers=headers,
                params={'size': 1},
                timeout=30
            )
            if events_response.status_code == 200:
                events_data = events_response.json()
                metrics['events'] = {
                    'count': events_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['events'] = {'count': 0, 'status': 'error', 'message': f'HTTP {events_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/eventmanagement/v3/events → HTTP {events_response.status_code}')
        except Exception as e:
            metrics['events'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/eventmanagement/v3/events → {str(e)}')
        
        # 5. Get VFC Flows Count
        try:
            vfc_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/visualflowcreator/v3/flows',
                headers=headers,
                params={'size': 1},
                timeout=30
            )
            if vfc_response.status_code == 200:
                vfc_data = vfc_response.json()
                metrics['vfc_flows'] = {
                    'count': vfc_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['vfc_flows'] = {'count': 0, 'status': 'error', 'message': f'HTTP {vfc_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/visualflowcreator/v3/flows → HTTP {vfc_response.status_code}')
        except Exception as e:
            metrics['vfc_flows'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/visualflowcreator/v3/flows → {str(e)}')
        
        # 6. Get Dashboard Count
        try:
            dashboards_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/kpidashboardconfiguration/v3/dashboards',
                headers=headers,
                params={'size': 1},
                timeout=30
            )
            if dashboards_response.status_code == 200:
                dashboards_data = dashboards_response.json()
                metrics['dashboards'] = {
                    'count': dashboards_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['dashboards'] = {'count': 0, 'status': 'error', 'message': f'HTTP {dashboards_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/kpidashboardconfiguration/v3/dashboards → HTTP {dashboards_response.status_code}')
        except Exception as e:
            metrics['dashboards'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/kpidashboardconfiguration/v3/dashboards → {str(e)}')
        
        # 7. Get Rules Count
        try:
            rules_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/rulesmanagement/v4/rules',
                headers=headers,
                params={'size': 1},
                timeout=30
            )
            if rules_response.status_code == 200:
                rules_data = rules_response.json()
                metrics['rules'] = {
                    'count': rules_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['rules'] = {'count': 0, 'status': 'error', 'message': f'HTTP {rules_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/rulesmanagement/v4/rules → HTTP {rules_response.status_code}')
        except Exception as e:
            metrics['rules'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/rulesmanagement/v4/rules → {str(e)}')
        
        # 8. Get Cases Count (if available)
        try:
            cases_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/casemanagement/v3/cases',
                headers=headers,
                params={'size': 1},
                timeout=30
            )
            if cases_response.status_code == 200:
                cases_data = cases_response.json()
                metrics['cases'] = {
                    'count': cases_data.get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['cases'] = {'count': 0, 'status': 'error', 'message': f'HTTP {cases_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/casemanagement/v3/cases → HTTP {cases_response.status_code}')
        except Exception as e:
            metrics['cases'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/casemanagement/v3/cases → {str(e)}')
        
        # 9. Get Predictions Count (AI/ML)
        try:
            predictions_response = requests.get(
                f'{INSIGHTS_HUB_API_BASE}/api/oipredictapi/v3/predict-assets/all',
                headers=headers,
                timeout=30
            )
            if predictions_response.status_code == 200:
                predictions_data = predictions_response.json()
                metrics['predictions'] = {
                    'count': predictions_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['predictions'] = {'count': 0, 'status': 'error', 'message': f'HTTP {predictions_response.status_code}'}
                errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/oipredictapi/v3/predict-assets/all → HTTP {predictions_response.status_code}')
        except Exception as e:
            metrics['predictions'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET {INSIGHTS_HUB_API_BASE}/api/oipredictapi/v3/predict-assets/all → {str(e)}')
        
        # 10. Get Anomaly Detection Count
        try:
            # Note: Using gateway endpoint for oipredictapi
            anomaly_response = requests.get(
                'https://gateway.eu1.mindsphere.io/api/oipredictapi/v3/usageDetails',
                headers=headers,
                params={'requestType': 'ANOMALY'},
                timeout=30
            )
            if anomaly_response.status_code == 200:
                anomaly_data = anomaly_response.json()
                metrics['anomaly_detections'] = {
                    'count': anomaly_data.get('page', {}).get('totalElements', 0),
                    'status': 'success'
                }
            else:
                metrics['anomaly_detections'] = {'count': 0, 'status': 'error', 'message': f'HTTP {anomaly_response.status_code}'}
                errors.append(f'GET https://gateway.eu1.mindsphere.io/api/oipredictapi/v3/usageDetails?requestType=ANOMALY → HTTP {anomaly_response.status_code}')
        except Exception as e:
            metrics['anomaly_detections'] = {'count': 0, 'status': 'error', 'message': str(e)}
            errors.append(f'GET https://gateway.eu1.mindsphere.io/api/oipredictapi/v3/usageDetails?requestType=ANOMALY → {str(e)}')
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'errors': errors if errors else None,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route(f'{BASE_PATH}/api/insights-hub/assets', methods=['GET'])
@app.route('/api/insights-hub/assets', methods=['GET'])
def get_insights_hub_assets():
    """Proxy endpoint to fetch assets from Insights Hub Asset Management API"""
    try:
        # Get authorization token from request headers (passed through by gateway)
        auth_header = request.headers.get('Authorization')
        # Insights Hub Asset Management API endpoint
        api_url = f'{INSIGHTS_HUB_API_BASE}/api/assetmanagement/v3/assets'
        
        # Get query parameters (for pagination, filtering, etc.)
        params = {
            'size': request.args.get('size', 10),  # Number of assets to return
            'page': request.args.get('page', 0),    # Page number
        }
        
        # Add filter if provided
        if request.args.get('filter'):
            params['filter'] = request.args.get('filter')
        
        # Make request to Insights Hub API
        headers = {
            'Authorization': user_auth_header,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        # Return the response from Insights Hub
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'data': response.json()
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Insights Hub API error: {response.status_code}',
                'details': response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Request to Insights Hub timed out'
        }), 504
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Failed to connect to Insights Hub: {str(e)}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route(f'{BASE_PATH}/api/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
