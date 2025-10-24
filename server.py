# server.py
import string
import random
import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = "super-secret-key"
socketio = SocketIO(app, async_mode="eventlet")

# Rooms structure:
# rooms = {
#   room_code: {
#       "token": "<secret-token>",
#       "members": { user_id: {"username":..., "sid": ...}, ... }
#   }
# }
rooms = {}

def gen_code(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

def gen_token(length=16):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("create_room")
def handle_create_room(data):
    username = (data.get("username") or "")[:32]
    if not username:
        emit("create_failed", {"msg": "Username required."})
        return

    room_code = gen_code()
    token = gen_token()
    user_id = str(uuid.uuid4())

    rooms[room_code] = {
        "token": token,
        "members": { user_id: {"username": username, "sid": request.sid} }
    }

    join_room(room_code)
    emit("room_created", {
        "room_code": room_code,
        "token": token,
        "user_id": user_id,
        "username": username
    }, to=request.sid)

    print(f"[create_room] {username} created room {room_code}")

@socketio.on("join_room_request")
def handle_join_room(data):
    username = (data.get("username") or "")[:32]
    room_code = (data.get("room_code") or "").upper()
    token = data.get("token") or ""

    if not username or not room_code or not token:
        emit("join_failed", {"msg": "username, room_code and token required."}, to=request.sid)
        return

    room = rooms.get(room_code)
    if not room:
        emit("join_failed", {"msg": "Room not found."}, to=request.sid)
        return

    if room["token"] != token:
        emit("join_failed", {"msg": "Invalid token."}, to=request.sid)
        return

    if len(room["members"]) >= 2:
        emit("join_failed", {"msg": "Room already has two participants."}, to=request.sid)
        return

    user_id = str(uuid.uuid4())
    room["members"][user_id] = {"username": username, "sid": request.sid}
    join_room(room_code)

    # notify both participants that join succeeded
    emit("joined_room", {
        "room_code": room_code,
        "user_id": user_id,
        "username": username,
        "members": {uid: {"username": m["username"]} for uid, m in room["members"].items()}
    }, room=room_code)

    print(f"[join_room] {username} joined room {room_code}")

@socketio.on("send_message")
def handle_send_message(data):
    room_code = (data.get("room_code") or "").upper()
    user_id = data.get("user_id") or ""
    text = data.get("text") or ""

    if not room_code or not user_id or not text:
        emit("error", {"msg": "room_code, user_id and text required."}, to=request.sid)
        return

    room = rooms.get(room_code)
    if not room:
        emit("error", {"msg": "Room not found."}, to=request.sid)
        return

    if user_id not in room["members"]:
        emit("error", {"msg": "You are not a member of this room."}, to=request.sid)
        return

    sender = room["members"][user_id]["username"]
    emit("message", {"room_code": room_code, "sender": sender, "text": text}, room=room_code)
    print(f"[message] {room_code} | {sender}: {text}")

@socketio.on("leave_room")
def handle_leave(data):
    room_code = (data.get("room_code") or "").upper()
    user_id = data.get("user_id") or ""

    room = rooms.get(room_code)
    if not room:
        return

    member = room["members"].pop(user_id, None)
    if member:
        leave_room(room_code)
        emit("system", {"msg": f"{member['username']} left the chat."}, room=room_code)

    if not room["members"]:
        rooms.pop(room_code, None)
        print(f"[room_closed] {room_code}")

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    removed = []
    for room_code, room in list(rooms.items()):
        for uid, info in list(room["members"].items()):
            if info["sid"] == sid:
                room["members"].pop(uid)
                emit("system", {"msg": f"{info['username']} disconnected."}, room=room_code)
                removed.append((room_code, uid))
        if not room["members"]:
            rooms.pop(room_code, None)
            print(f"[room_closed] {room_code}")
    if removed:
        print(f"[disconnect] removed: {removed}")

if __name__ == "__main__":
    print("✅ Sentinel server ready (Render-compatible).")
    socketio.run(app, host="0.0.0.0", port=10000)
