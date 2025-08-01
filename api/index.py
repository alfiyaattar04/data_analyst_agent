from flask import Flask, request, jsonify
import os
import sys
import tempfile
import asyncio
from werkzeug.utils import secure_filename

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

# Import modules
try:
    from agent import DataAnalystAgent
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {current_dir}")
    print(f"Project root: {project_root}")
    print(f"Src path: {src_path}")
    print(f"Sys path: {sys.path}")
    raise

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size


@app.route('/api/', methods=['POST'])
def analyze_data():
    try:
        # Handle different input formats
        question_text = ""

        # Check for file upload
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                content = file.read().decode('utf-8')
                question_text = content

        # Check for form data (curl -F "@question.txt")
        elif len(request.files) > 0:
            # Handle curl -F "@question.txt" format
            for key in request.files:
                file = request.files[key]
                content = file.read().decode('utf-8')
                question_text = content
                break

        elif request.is_json:
            data = request.get_json()
            question_text = data.get('question', '')

        else:
            # Handle raw text data
            question_text = request.data.decode('utf-8')

        if not question_text.strip():
            return jsonify({'error': 'No question provided'}), 400

        # Initialize agent and process request
        agent = DataAnalystAgent()
        result = asyncio.run(agent.process_request(question_text))

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'Data Analyst Agent API',
        'endpoint': '/api/',
        'method': 'POST',
        'description': 'Send data analysis tasks via POST request'
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
