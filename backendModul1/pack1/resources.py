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
        data = {
            "Subject": ticket_data.get('subject'),
            "Description:": ticket_data.get('description'),
            "Status:": ticket_data.get('status'),
            "Priority:": ticket_data.get('priority')
        }

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

# current_param_index = 0  # Start with the first parameter
# parameter_order = ["subject", "description", "email", "priority", "status"]
class ChatBot(Namespace):
    def on_connect(self):
        print('Client Connected')

    def on_message(self, message):
        cur = mysql.connection.cursor()
        user_id = int(redis_client.get('user_id'))

        if user_id not in user_states:
            user_states[user_id] = {'step': 0, 'subject': '', 'description': '', 'email': '', 'priority': '', 'status': ''}

        state = user_states[user_id]

        try:
            if state['step'] == 0:
                if message.lower() == 'create ticket':
                    cur.execute('SELECT * FROM process WHERE process_name = %s', (message,))
                    process_name = cur.fetchone()
                    if not process_name:
                        response = "Process not found. Please try again."
                        emit('response', response)
                        return

                    params = json.loads(process_name[2])['params']
                    session['subject'] = params[0]
                    session['description'] = params[1]
                    session['email'] = params[2]
                    session['priority'] = params[3]
                    session['status'] = params[4]

                    # Prompt for subject
                    cur.execute('SELECT message FROM message WHERE message_name = %s', (session['subject'],))
                    pmessage = cur.fetchone()
                    prompt_message = json.loads(pmessage[0])['prompt']
                    state['step'] = 1
                    return emit('response', prompt_message)

                else:
                    response = "I didn't understand that. Please say 'Create A Ticket' to start."
                    emit('response', response)

            elif state['step'] == 1:
                state['subject'] = message
                # Prompt for description
                cur.execute('SELECT message FROM message WHERE message_name = %s', (session['description'],))
                pmessage = cur.fetchone()
                prompt_message = json.loads(pmessage[0])['prompt']
                state['step'] = 2
                return emit('response', prompt_message)


            elif state['step'] == 2:
                state['description'] = message
                cur.execute('SELECT message FROM message WHERE message_name = %s', (session['email'],))
                pmessage = cur.fetchone()
                prompt_message = json.loads(pmessage[0])['prompt']
                state['step'] = 3
                return emit('response', prompt_message)


            elif state['step'] == 3:
                state['email'] = message
                cur.execute('SELECT message FROM message WHERE message_name = %s', (session['priority'],))
                pmessage = cur.fetchone()
                prompt_message = json.loads(pmessage[0])['prompt']
                state['step'] = 4
                return emit('response', prompt_message)

            elif state['step'] == 4:
                state['priority'] = message
                cur.execute('SELECT message FROM message WHERE message_name = %s', (session['status'],))
                pmessage = cur.fetchone()
                prompt_message = json.loads(pmessage[0])['prompt']
                state['step'] = 5
                return emit('response', prompt_message)

            elif state['step'] == 5:
                state['status'] = message
                ticket_response = create_ticket(state['subject'], state['description'], state['email'], state['priority'], state['status'])
                user_states[user_id] = {'step': 0, 'subject': '', 'description': '', 'email': ''}
                return emit('response', ticket_response)
                # Reset state for next interaction


            elif message.lower() in ['view a ticket', '2', 'view a ticket']:
                ticket_id = int(redis_client.get('ticket_id'))
                response = view_ticket(ticket_id)
                emit('response', response)

        except Exception as e:
            print(f"An error occurred: {e}")
            emit('response', "An error occurred while processing your request.")
        finally:
            cur.close()
