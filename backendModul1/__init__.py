from flask import Flask
from flask_cors import CORS
from flask_restful import Api
from flask_socketio import SocketIO
from flask_mysqldb import MySQL
from flask_redis import FlaskRedis
import importlib


app = Flask(__name__)
api = Api(app)
socketio = SocketIO(app, origins=["http://127.0.0.1:6010"], cors_allowed_origins="*")

CORS(app)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'ticket'

app.config['REDIS_URL'] = "redis://localhost:6379/0"
redis_client = FlaskRedis(app)

mysql = MySQL(app)
app.secret_key = '76426856534'

importlib.import_module('backendModul1.pack1')