from flask import Flask
from flask_cors import CORS
from app.routes.daily_waste_chart import cas_dash, cbme_dash, cte_dash
from app.routes.fill_level import fill_level_bp

app = Flask(__name__)
cas_dash(app)
cte_dash(app)
cbme_dash(app)

CORS(app, resources={
    r"/*": {"origins": {"https://ebasura.online", "https://www.ebasura.online", "http://192.168.0.125:8000"}}})

app.register_blueprint(fill_level_bp)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
