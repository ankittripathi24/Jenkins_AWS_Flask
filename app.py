from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Support for base path (for Insights Hub/MindSphere deployment)
BASE_PATH = os.environ.get('BASE_PATH', '').rstrip('/')

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
