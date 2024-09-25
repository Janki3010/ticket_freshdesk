from module1 import api
from module1.pack1.resources import *

api.add_resource(Register,'/register')
api.add_resource(Login,'/login')
api.add_resource(ChatBot, '/chat')