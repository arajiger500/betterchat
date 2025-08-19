from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import sqlite3
from datetime import datetime
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'  # change this later!
socketio = SocketIO(app, cors_allowed_origins="*")

online_users = {}  # sid -> username


# ---------------------- DB HELPERS ----------------------

def get_db():
    conn = sqlite3.connect('chat.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            reply_id TEXT,
            FOREIGN KEY (reply_id) REFERENCES messages(id)
        )
    ''')
    conn.commit()
    conn.close()


def save_message(msg_id, username, text, timestamp, reply_id=None):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO messages (id, username, text, timestamp, reply_id) VALUES (?,?,?,?,?)',
              (msg_id, username, text, timestamp, reply_id))
    conn.commit()
    conn.close()


def get_messages():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM messages ORDER BY timestamp')
    rows = c.fetchall()
    conn.close()

    messages = []
    for row in rows:
        msg = {
            'id': row['id'],
            'username': row['username'],
            'text': row['text'],
            'timestamp': row['timestamp'],
            'reply': None
        }
        if row['reply_id']:
            reply_msg = get_message_by_id(row['reply_id'])
            if reply_msg:
                msg['reply'] = {
                    'id': reply_msg['id'],
                    'username': reply_msg['username'],
                    'text': reply_msg['text']
                }
        messages.append(msg)
    return messages


def get_message_by_id(msg_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM messages WHERE id=?', (msg_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_message(msg_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM messages WHERE id=?', (msg_id,))
    conn.commit()
    conn.close()


# ---------------------- ROUTES ----------------------

@app.route('/')
def index():
    messages = get_messages()
    return render_template('index.html', messages=messages)


# ---------------------- SOCKET EVENTS ----------------------

@socketio.on('new_user')
def handle_new_user(username):
    online_users[request.sid] = username
    emit('online_users', list(online_users.values()), broadcast=True)
    emit('system_message', f"{username} joined the chat.", broadcast=True)


@socketio.on('send_message')
def handle_send_message(msg):
    msg_id = str(uuid.uuid4())  # safe unique ID
    timestamp = datetime.utcnow().isoformat()

    reply_id = msg['reply']['id'] if msg.get('reply') else None

    save_message(msg_id, msg['username'], msg['text'], timestamp, reply_id)

    msg_to_send = {
        'id': msg_id,
        'username': msg['username'],
        'text': msg['text'],
        'timestamp': timestamp,
        'reply': msg['reply'] if reply_id else None
    }

    emit('new_message', msg_to_send, broadcast=True)


@socketio.on('delete_message')
def handle_delete_message(msg_id):
    delete_message(msg_id)
    emit('delete_message', msg_id, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        username = online_users.pop(request.sid)
        emit('online_users', list(online_users.values()), broadcast=True)
        emit('system_message', f"{username} left the chat.", broadcast=True)


# ---------------------- MAIN ----------------------

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)