from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import speech_recognition as sr
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variable to track if voice recognition is active
voice_recognition_active = False
recognition_thread = None


@app.route("/")
def index():
    return render_template("game.html")  # Will serve the game.html from templates folder


def recognize_speech():
    """Continuously listen for speech and emit commands to the client"""
    global voice_recognition_active
    recognizer = sr.Recognizer()

    # Using microphone as source
    while voice_recognition_active:
        try:
            with sr.Microphone() as source:
                print("🎤 Listening for voice commands...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=2)

            try:
                command = recognizer.recognize_google(audio).lower()
                print(f"✅ Recognized: {command}")
                socketio.emit('voice_command', {'command': command})

                # Slight delay to prevent too many rapid recognitions
                time.sleep(0.5)

            except sr.UnknownValueError:
                print("⚠️ Could not understand audio")
            except sr.RequestError as e:
                print(f"❌ Error: {e}")

        except Exception as e:
            print(f"Error in speech recognition loop: {e}")
            time.sleep(1)  # Prevent rapid error loops


@socketio.on('start_listening')
def handle_start_listening():
    """Start voice recognition in a separate thread"""
    global voice_recognition_active, recognition_thread

    if voice_recognition_active:
        return  # Already running

    voice_recognition_active = True
    recognition_thread = threading.Thread(target=recognize_speech)
    recognition_thread.daemon = True  # Thread will exit when main program exits
    recognition_thread.start()

    emit('status', {'message': 'Listening started'})
    print("Voice recognition started")


@socketio.on('stop_listening')
def handle_stop_listening():
    """Stop voice recognition"""
    global voice_recognition_active

    voice_recognition_active = False
    emit('status', {'message': 'Listening stopped'})
    print("Voice recognition stopped")


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print("Client connected")
    emit('status', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    global voice_recognition_active

    # Turn off voice recognition when client disconnects
    voice_recognition_active = False
    print("Client disconnected")


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5050)