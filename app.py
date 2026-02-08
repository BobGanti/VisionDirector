
import os
import json
from flask import Flask, send_from_directory, render_template_string

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    # Read the index.html file
    try:
        with open('index.html', 'r') as f:
            html_content = f.read()
        
        # Securely inject the API_KEY into a browser-friendly process.env shim.
        # Use JSON encoding so quotes/special chars cannot break the HTML.
        api_key = os.environ.get('API_KEY', '')
        api_key_literal = json.dumps(api_key)
        env_shim = f'<script>var process = {{ env: {{ API_KEY: {api_key_literal} }} }}; window.process = process;</script>'
        
        # Inject the shim into the head
        result = html_content.replace('<head>', f'<head>\n  {env_shim}')
        return render_template_string(result)
    except Exception as e:
        return f"Error loading index.html: {str(e)}", 500

@app.route('/<path:path>')
def static_proxy(path):
    # Serve static files (JS, CSS, Images) from the root directory
    return send_from_directory('.', path)

if __name__ == '__main__':
    # Cloud Run expects the app to listen on the port defined by the PORT env var
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
