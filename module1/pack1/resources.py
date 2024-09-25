from flask_restful import Resource
from flask import redirect, make_response, render_template, request
import requests


class Register(Resource):
    def get(self):
        return make_response(render_template('register.html'))

    def post(self):
        data = {
            "username": request.form['username'],
            "email": request.form['email'],
            "password": request.form['password'],
            "mobile": request.form['phone'],
        }

        response = requests.post('http://127.0.0.1:6010/register', json=data)

        if response.status_code == 200:
            return redirect('http://127.0.0.1:6007/login')
        else:
            return make_response({"error": "Failed to insert data into the database"}, 500)


class Login(Resource):
    def get(self):
        return make_response(render_template('login.html'))

    def post(self):
        data = {
            "email": request.form['email'],
            "password": request.form['password']
        }

        response = requests.post('http://127.0.0.1:6010/login', json=data)

        if response.status_code == 200:
            return redirect('http://127.0.0.1:6007/chat')
        else:
            return make_response({"error": "Failed to Login"}, 500)


class ChatBot(Resource):
    def get(self):
        return make_response(render_template('chatbot.html'))
