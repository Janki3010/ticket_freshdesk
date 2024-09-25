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


def create_ticket(subject, description, email):
    url = f'https://{domain}.freshdesk.com/api/v2/tickets'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'subject': subject,
        'description': description,
        'email': email,
        'priority': 1,
        'status': 2
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
        data = {
            "Subject": ticket_data.get('subject'),
            "Description:": ticket_data.get('description'),
            "Status:": ticket_data.get('status'),
            "Priority:": ticket_data.get('priority')
        }
        # print("Ticket Details:")
        # print("Subject:", ticket_data.get('subject'))
        # print("Description:", ticket_data.get('description'))
        # print("Status:", ticket_data.get('status'))
        # print("Priority:", ticket_data.get('priority'))
        return json.dumps(data)
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


class ChatBot(Namespace):
    def on_connect(self):
        print('Client Connected')

    def on_message(self, message):
        user_id = int(redis_client.get('user_id'))
        print(user_states)
        if user_id not in user_states:
            user_states[user_id] = {'step': 0, 'subject': '', 'description': '', 'email': ''}

        state = user_states[user_id]

        if state['step'] == 0:
            if message in ['Hii', 'Hello']:
                response = 'Hello! How can I help you? 1. Create A Ticket 2. View A Ticket'
            elif message in ['View A Ticket', '2', 'view a ticket']:
                ticket_id = int(redis_client.get('ticket_id'))
                response = view_ticket(ticket_id)


            elif message in ['Create A Ticket', '1', 'create a ticket']:
                response = "Please provide the issue-related subject."
                state['step'] = 1
            else:
                response = "I didn't understand that. Please say 'Create A Ticket' to start."

        elif state['step'] == 1:
            state['subject'] = message
            response = "Please provide the description of the issue."
            state['step'] = 2

        elif state['step'] == 2:
            state['description'] = message
            response = "Please provide your email."
            state['step'] = 3

        elif state['step'] == 3:
            state['email'] = message
            ticket_response = create_ticket(state['subject'], state['description'], state['email'])
            response = ticket_response
            state['step'] = 0

        emit('response', response)

        user_states[user_id] = state
