from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, send
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app, cors_allowed_origins="*")

online_users = {}  # username

conn = sqlite3.connect('chat.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        username TEXT,
        text TEXT,
        timestamp TEXT,
        reply_id TEXT
    )
''')
conn.commit()

@app.route('/')
def index():
    # Geçmiş mesajları alma
    c.execute('SELECT id, username, text, timestamp, reply_id FROM messages ORDER BY timestamp')
    rows = c.fetchall()
    messages = []
    for row in rows:
        msg = {
            'id': row[0],
            'username': row[1],
            'text': row[2],
            'timestamp': row[3],
            'reply': None
        }
        if row[4]:
            # reply_id varsa onu alma
            c.execute('SELECT username, text FROM messages WHERE id=?', (row[4],))
            reply_row = c.fetchone()
            if reply_row:
                msg['reply'] = {'username': reply_row[0], 'text': reply_row[1], 'id': row[4]}
        messages.append(msg)
    return render_template('index.html', messages=messages)

# Yeni kullanıcı haberi
@socketio.on('new_user')
def handle_new_user(username):
    online_users[request.sid] = username
    emit('online_users', list(online_users.values()), broadcast=True)

# Mesaj gönderme
@socketio.on('send_message')
def handle_send_message(msg):
    msg_id = msg['timestamp'] + msg['username'] + msg['text']  # benzersiz ID
    msg['id'] = msg_id

    
    reply_id = msg['reply']['id'] if msg['reply'] else None
    c.execute('INSERT INTO messages (id, username, text, timestamp, reply_id) VALUES (?,?,?,?,?)',
              (msg_id, msg['username'], msg['text'], msg['timestamp'], reply_id))
    conn.commit()

    send(msg, broadcast=True)

# Mesaj silme
@socketio.on('delete_message')
def handle_delete_message(msg_id):
    # DB'den sil
    c.execute('DELETE FROM messages WHERE id=?', (msg_id,))
    conn.commit()
    emit('delete_message', msg_id, broadcast=True)

# Kullanıcı ayrılma haberi
@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        username = online_users.pop(request.sid)
        emit('online_users', list(online_users.values()), broadcast=True)
        send({'username':'SYSTEM','text':f"{username} sohbettan ayrıldı.",'timestamp':'','reply':None}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001)
