from flask import Flask, request, jsonify
from flask_cors import CORS
import face_recognition
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- DATABASE ----------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS children (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image TEXT,
    encoding BLOB,
    email TEXT,
    location TEXT
)
""")
conn.commit()

# ---------- EMAIL ----------
def send_email(to_email):
    sender = "your_email@gmail.com"
    password = "your_app_password"

    msg = MIMEText("Child Match Found!")
    msg["Subject"] = "ALERT 🚨"
    msg["From"] = sender
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)

# ---------- SIGNUP ----------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?)", (data["email"], data["password"]))
        conn.commit()
        return jsonify({"msg": "Signup success"})
    except:
        return jsonify({"msg": "User exists"})

# ---------- LOGIN ----------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (data["email"], data["password"]))
    user = cursor.fetchone()

    if user:
        return jsonify({"msg": "Login success"})
    return jsonify({"msg": "Invalid credentials"}), 401

# ---------- UPLOAD ----------
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["image"]
    email = request.form["email"]
    location = request.form["location"]

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    img = face_recognition.load_image_file(path)
    encodings = face_recognition.face_encodings(img)

    if len(encodings) == 0:
        return jsonify({"msg": "No face detected"})

    encoding_bytes = encodings[0].tobytes()

    cursor.execute(
        "INSERT INTO children (image, encoding, email, location) VALUES (?, ?, ?, ?)",
        (path, encoding_bytes, email, location)
    )
    conn.commit()

    return jsonify({"msg": "Child uploaded successfully"})

# ---------- CROSSCHECK ----------
@app.route("/crosscheck", methods=["POST"])
def crosscheck():
    file = request.files["image"]
    temp_path = os.path.join(UPLOAD_FOLDER, "temp.jpg")
    file.save(temp_path)

    img = face_recognition.load_image_file(temp_path)
    encodings = face_recognition.face_encodings(img)

    if len(encodings) == 0:
        return jsonify({"msg": "No face detected"})

    input_encoding = encodings[0]

    cursor.execute("SELECT encoding, email FROM children")
    records = cursor.fetchall()

    for enc_bytes, email in records:
        known_encoding = face_recognition.face_encodings(
            face_recognition.load_image_file(temp_path)
        )

        # convert back
        import numpy as np
        known_encoding = np.frombuffer(enc_bytes, dtype=np.float64)

        match = face_recognition.compare_faces([known_encoding], input_encoding)

        if match[0]:
            send_email(email)
            return jsonify({"msg": "MATCH FOUND ✅ Email sent"})

    return jsonify({"msg": "NOT FOUND ❌"})

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
