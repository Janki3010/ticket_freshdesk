from backendModul1 import api, app, socketio
from backendModul1.pack1.resources import *

api.add_resource(Register, '/register')
api.add_resource(Login, '/login')
socketio.on_namespace(ChatBot('/chat'))
