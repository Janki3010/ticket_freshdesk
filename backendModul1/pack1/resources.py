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
        # redis_client.set('ticket_id', ticket_id)
        return f"Ticket created successfully with ID: {ticket_id}"
    else:
        print(f"Failed to create ticket: {response.status_code}, {response.text}")
        return f"Failed to create ticket: {response.status_code}, {response.text}"


def view_ticket(email):
    # url = f'https://{domain}.freshdesk.com/api/v2/tickets/{ticket_id}'
    url = f'https://{domain}.freshdesk.com/api/v2/tickets?email={email}'
    response = requests.get(url, auth=(api_key, 'X'))

    if response.status_code == 200:
        ticket_data = response.json()
        view_data = []
        for i in ticket_data:
            ticket_info = {
                'id': i['id'],
                'subject': i['subject'],
                'status': i['status'],
                'priority': i['priority']
            }
            view_data.append(ticket_info)
        return json.dumps(view_data)
    else:
        print("Failed to retrieve ticket:", response.status_code, response.text)


def update_ticket(ticket_id, priority, status):
    url = f'https://{domain}.freshdesk.com/api/v2/tickets/{ticket_id}'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'priority': priority,
        'status': status
    }

    response = requests.put(url, headers=headers, json=data, auth=HTTPBasicAuth(api_key, 'X'))
    if response.status_code == 200:
        return 'Updated successfully'
    else:
        return 'Something wrong, Not able to update'


def delete_ticket(ticket_id):
    url = f'https://{domain}.freshdesk.com/api/v2/tickets/{ticket_id}'
    response = requests.delete(url, auth=HTTPBasicAuth(api_key, 'X'))
    if response.status_code == 204:
        return f'{ticket_id} ticket deleted successfully'
    elif response.status_code == 405:
        return f'{ticket_id} ticket is not exist'
    else:
        return f'Not able to delete {ticket_id} this ticket'


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
        cur.execute('SELECT * FROM ticket.users WHERE email = %s and password = %s', (email, password))
        account = cur.fetchone()
        cur.close()
        if account:
            user_id = account[0]
            email = account[2]
            session['loggedin'] = True
            session['id'] = account[0]
            redis_client.set('user_id', user_id)
            redis_client.set('email', email)
            return {'message': 'success', 'user_id': user_id}, 200
        else:
            return {'message': 'user not found'}, 404


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

        if message in ['Hello', 'Hii', 'hii', 'hello']:
            emit('response', 'create ticket, view ticket, update ticket, delete ticket')
            return

        if message in ['view ticket']:
            email = redis_client.get('email')
            email = email.decode('utf-8')
            view_data = view_ticket(email)
            emit('response', view_data)
            return

        if user_id not in user_states:
            user_states[user_id] = {'step': 0, 'data': {}, 'delete_step': 0, 'update_step': 0}

        state = user_states[user_id]

        if state['delete_step'] == 0 and message == 'delete ticket':
            emit('response', 'Give me a ticket_id to delete the ticket')
            state['delete_step'] = 1
            return
        elif state['delete_step'] == 1:
            ticket_id = message
            emit('response', delete_ticket(ticket_id))
            state['delete_step'] = 0
            return

        if state['update_step'] == 0 and message == 'update ticket':
            emit('response', 'Give me a ticket_id to update the ticket')
            state['update_step'] = 1
            return
        elif state['update_step'] == 1:
            try:
                state['tid'] = int(message)
                # emit('response', 'Please enter the status (2 for open, 3 for Pending,4 for Resolved, 5 for Closed)')
                emit('response',  self.get_prompt(cur, 'status'))
                state['update_step'] = 2
                return
            except ValueError:
                emit('response', 'Invalid ticket_id. Please provide a numeric ticket ID.')
                return
        elif state['update_step'] == 2:
            try:
                state['status'] = int(message)
                # emit('response', 'Please enter the priority (1-5) Low-1,Medium-2,High-3,Urgent-4')
                emit('response', self.get_prompt(cur, 'priority'))
                state['update_step'] = 3
                return
            except ValueError:
                emit('response', 'Invalid status. Please provide a numeric status.')
                return
        elif state['update_step'] == 3:
            try:
                priority = int(message)
                result = update_ticket(state['tid'], priority, state['status'])
                emit('response', result)
                state['update_step'] = 0
                return
            except ValueError:
                emit('response', 'Invalid priority. Please provide a numeric priority.')
                return

        if state['step'] == 0 and message.lower() == 'create ticket':
            cur.execute('SELECT * FROM process WHERE process_name = %s', (message,))
            process = cur.fetchone()
            if not process:
                emit('response', "Process not found. Please try again.")
                return

            params = json.loads(process[2])['params']
            state['data'] = {param: None for param in params}

            emit('response', self.get_prompt(cur, 'subject'))
            state['step'] = 1
            return
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

