from flask import Flask, render_template, request, redirect, url_for
import requests

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/submit', methods=['POST'])
def submit():
    answers = request.json.get('answers')
    category = answers.get('category') if isinstance(answers, dict) else None
    payload = {
        'answers': answers,
        'category': category,
    }
    # Quick health-check before attempting /analyze so we can return clearer errors
    try:
        health = requests.get('http://localhost:8000/health', timeout=2)
        if health.status_code != 200:
            return {'error': 'Analysis service unhealthy', 'details': f'status={health.status_code} body={health.text}'}, 502
    except requests.exceptions.RequestException as e:
        return {'error': 'Analysis service unreachable', 'details': str(e)}, 502

    try:
        resp = requests.post('http://localhost:8000/analyze', json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        # include response text if available
        details = str(e)
        if hasattr(e, 'response') and e.response is not None:
            details = f'status={e.response.status_code} body={e.response.text}'
        return {'error': 'Failed to contact analysis service', 'details': details}, 502

@app.route('/result')
def result():
    career = request.args.get('career')
    return render_template('result.html', career=career)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000,debug=True) 
