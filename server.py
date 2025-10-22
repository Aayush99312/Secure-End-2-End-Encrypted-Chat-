# server.py
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

users = set()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('register')
def register(data):
    username = data.get('username')
    if username:
        users.add(username)
        emit('system', {'msg': f"{username} joined the chat"}, broadcast=True)

@socketio.on('message')
def handle_message(data):
    sender = data.get('sender')
    text = data.get('text')
    if sender and text:
        emit('message', {'sender': sender, 'msg': text}, broadcast=True)

@socketio.on('disconnect')
def disconnect():
    emit('system', {'msg': "A user has disconnected"}, broadcast=True)

if __name__ == '__main__':
    print("✅ Server running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
