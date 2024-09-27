from flask import session, request
from flask_restful import Resource
from flask_socketio import Namespace, emit
import requests
import json

from requests.auth import HTTPBasicAuth

from backendModul1 import mysql, redis_client

api_key = 'ocBecqBBIfasHQUZlbKp'
domain = 'techtik'
user_states = {}


def create_ticket(subject, description, email, priority, status):
    url = f'https://{domain}.freshdesk.com/api/v2/tickets'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'subject': subject,
        'description': description,
        'email': email,
        'priority': int(priority),
        'status': int(status)
    }

    response = requests.post(url, headers=headers, json=data, auth=HTTPBasicAuth(api_key, 'X'))

    if response.status_code == 201:
        ticket_id = response.json().get('id')
        # session['ticket_id'] = ticket_id
        redis_client.set('ticket_id', ticket_id)
        return f"Ticket created successfully with ID: {ticket_id}"
    else:
        print(f"Failed to create ticket: {response.status_code}, {response.text}")
        return f"Failed to create ticket: {response.status_code}, {response.text}"


def view_ticket(ticket_id):
    url = f'https://{domain}.freshdesk.com/api/v2/tickets/{ticket_id}'
    response = requests.get(url, auth=(api_key, 'X'))

    if response.status_code == 200:
        ticket_data = response.json()
        view_data = {
            "Subject": ticket_data.get('subject'),
            "Description:": ticket_data.get('description'),
            "Status:": ticket_data.get('status'),
            "Priority:": ticket_data.get('priority')
        }
        return json.dumps(view_data)
    else:
        print("Failed to retrieve ticket:", response.status_code, response.text)


class Register(Resource):
    def post(self):
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        mobile = data.get('mobile')

        cur = mysql.connection.cursor()
        cur.callproc('add_user_data', (username, email, password, mobile))
        mysql.connection.commit()
        cur.close()

        return {"message": "Data inserted successfully"}, 200


class Login(Resource):
    def post(self):
        data = request.json
        email = data.get('email')
        password = data.get('password')

        cur = mysql.connection.cursor()
        cur.execute('select * from users where email = %s and password = %s', (email, password))
        account = cur.fetchone()
        cur.close()
        if account:
            user_id = account[0]
            session['loggedin'] = True
            session['id'] = account[0]
            redis_client.set('user_id', user_id)
            return {'message': 'success', 'user_id': user_id}, 200
        else:
            return {'message': 'user not found'}, 404


import json
from flask_socketio import emit
from flask_mysqldb import MySQL

class ChatBot(Namespace):
    def on_connect(self):
        print('Client Connected')

    def get_prompt(self, cur, key):
        cur.execute('SELECT message FROM message WHERE message_name = %s', (key,))
        pmessage = cur.fetchone()
        return json.loads(pmessage[0])['prompt'] if pmessage else "No prompt found."

    def on_message(self, message):
        cur = mysql.connection.cursor()
        user_id = int(redis_client.get('user_id'))

        if user_id not in user_states:
            user_states[user_id] = {'step': 0, 'data': {}}

        state = user_states[user_id]

        if message in ['view a ticket', '2']:
            ticket_id = int(redis_client.get('ticket_id'))
            view_data = view_ticket(ticket_id)
            emit('response', view_data)
            return

        if state['step'] == 0:
            if message.lower() == 'create ticket':
                cur.execute('SELECT * FROM process WHERE process_name = %s', (message,))
                process = cur.fetchone()
                if not process:
                    emit('response', "Process not found. Please try again.")
                    return

                params = json.loads(process[2])['params']
                state['data'] = {
                    'subject': None,
                    'description': None,
                    'email': None,
                    'priority': None,
                    'status': None
                }

                emit('response', self.get_prompt(cur, 'subject'))
                state['step'] = 1
                return
            else:
                emit('response', "Please say 'create ticket")

        elif 1 <= state['step'] < 5:
            key = ['subject', 'description', 'email', 'priority', 'status']
            state['data'][key[state['step'] - 1]] = message
            if state['step'] < 5:
                emit('response', self.get_prompt(cur, key[state['step']]))
            else:
                emit('response', "Please confirm your ticket details.")
            state['step'] += 1
        elif state['step'] == 5:
            state['data']['status'] = message
            ticket_response = create_ticket(**state['data'])
            user_states[user_id] = {'step': 0, 'data': {}}
            emit('response', ticket_response)


