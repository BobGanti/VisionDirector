import os
from flask import Flask, send_from_directory, render_template_string

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()

        api_key = os.environ.get('API_KEY', '')  # Google key (existing behaviour)
        openai_key = os.environ.get('OPENAI_API_KEY', '')  # for Baby Step 3+

        env_shim = (
            '<script>'
            'window.process = window.process || { env: {} };'
            'window.process.env = window.process.env || {};'
            f'window.process.env.API_KEY = "{api_key}";'
            f'window.process.env.OPENAI_API_KEY = "{openai_key}";'
            '</script>'
        )

        result = html_content.replace('<head>', f'<head>\n  {env_shim}', 1)
        return render_template_string(result)
    except Exception as e:
        return f"Error loading index.html: {str(e)}", 500

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
