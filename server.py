# server.py
import io
from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, async_mode="eventlet")

# ===== In-Memory Data =====
rooms = {}          # room_code -> {"users": set(), "messages": []}
temp_files = {}     # file_id -> bytes

@app.route("/")
def index():
    return render_template("index.html")

# --- Handle user join ---
@socketio.on("join")
def handle_join(data):
    username = data.get("username")
    room = data.get("room")
    if not username or not room:
        return
    join_room(room)

    if room not in rooms:
        rooms[room] = {"users": set(), "messages": []}
    rooms[room]["users"].add(username)

    emit("system", {"msg": f"{username} joined room {room}"}, to=room)

# --- Handle text message ---
@socketio.on("message")
def handle_message(data):
    username = data.get("username")
    room = data.get("room")
    msg = data.get("msg")

    if not room or room not in rooms:
        return

    rooms[room]["messages"].append((username, msg))
    emit("message", {"username": username, "msg": msg}, to=room)

# --- Handle file/image upload ---
@socketio.on("upload")
def handle_upload(data):
    """
    data: {
        "username": "...",
        "room": "...",
        "filename": "...",
        "filedata": base64 string
    }
    """
    import base64, uuid
    room = data.get("room")
    if not room or room not in rooms:
        return

    file_id = str(uuid.uuid4())
    file_bytes = base64.b64decode(data["filedata"])
    temp_files[file_id] = file_bytes

    emit(
        "file",
        {
            "username": data["username"],
            "filename": secure_filename(data["filename"]),
            "file_id": file_id,
        },
        to=room,
    )

@app.route("/file/<file_id>")
def get_file(file_id):
    if file_id not in temp_files:
        return "Expired or deleted", 404
    file_bytes = temp_files[file_id]
    return send_file(
        io.BytesIO(file_bytes),
        as_attachment=True,
        download_name="download",
    )

# --- Handle user leaving ---
@socketio.on("leave")
def handle_leave(data):
    username = data.get("username")
    room = data.get("room")
    if not room or room not in rooms:
        return
    leave_room(room)
    rooms[room]["users"].discard(username)
    emit("system", {"msg": f"{username} left"}, to=room)

    # If everyone left -> clean up memory
    if not rooms[room]["users"]:
        del rooms[room]
        # Purge all temporary files
        temp_files.clear()

# --- On disconnect (browser closed) ---
@socketio.on("disconnect")
def handle_disconnect():
    # Full cleanup happens when room empties
    pass

if __name__ == "__main__":
    print("✅ Secure Chat Server running...")
    socketio.run(app, host="0.0.0.0", port=10000)
