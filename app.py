from flask import Flask
import os

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'GreyMatters'


@app.route('/health')
def health():
    return 'OK', 200


if __name__ == "__main__":
    # Use the PORT environment variable that Render provides
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
