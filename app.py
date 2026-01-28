from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Support for base path (for Insights Hub/MindSphere deployment)
BASE_PATH = os.environ.get('BASE_PATH', '').rstrip('/')

# Insights Hub API base URL (update if different)
INSIGHTS_HUB_API_BASE = os.environ.get('INSIGHTS_HUB_API_BASE', 'https://gateway.eu1.mindsphere.io')

# Store submissions in memory (in production, use a database)
submissions = []

@app.route(f'{BASE_PATH}/')
@app.route('/')
def index():
    """Render the main UI page"""
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

@app.route(f'{BASE_PATH}/api/insights-hub/assets', methods=['GET'])
@app.route('/api/insights-hub/assets', methods=['GET'])
def get_insights_hub_assets():
    """Proxy endpoint to fetch assets from Insights Hub Asset Management API"""
    try:
        # Get authorization token from request headers (passed through by gateway)
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'No authorization token provided'
            }), 401
        
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
            'Authorization': auth_header,
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
