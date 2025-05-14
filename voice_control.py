import speech_recognition as sr
import threading
import time
from flask_socketio import SocketIO, emit


class VoiceController:
    def __init__(self, socketio):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.socketio = socketio
        self.is_listening = False
        self.listening_thread = None

    def start_listening(self):
        """Start voice command listening in a separate thread"""
        if not self.is_listening:
            self.is_listening = True
            self.listening_thread = threading.Thread(target=self._listen_loop)
            self.listening_thread.daemon = True
            self.listening_thread.start()
            print("Voice command system activated")
            return True
        return False

    def stop_listening(self):
        """Stop the listening loop"""
        if self.is_listening:
            self.is_listening = False
            if self.listening_thread:
                self.listening_thread.join(timeout=1.0)
            print("Voice command system deactivated")
            return True
        return False

    def _listen_loop(self):
        """Main listening loop that runs in a separate thread"""
        with self.microphone as source:
            # Adjust for ambient noise once at the beginning
            self.recognizer.adjust_for_ambient_noise(source)
            print("Listening for commands...")

            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=2.0)
                    try:
                        command = self.recognizer.recognize_google(audio).lower()
                        print(f"Recognized: {command}")
                        self._process_command(command)
                    except sr.UnknownValueError:
                        # Didn't recognize anything, just continue
                        pass
                    except sr.RequestError as e:
                        print(f"Speech recognition service error: {e}")
                except Exception as e:
                    if self.is_listening:  # Only show error if we're still supposed to be listening
                        print(f"Listening error: {e}")

                # Small delay to prevent CPU overuse
                time.sleep(0.1)

    def _process_command(self, command):
        """Process the recognized voice command"""
        # Direction commands
        if "up" in command:
            self.socketio.emit('move_snake', {'direction': 'up'})
        elif "down" in command:
            self.socketio.emit('move_snake', {'direction': 'down'})
        elif "left" in command:
            self.socketio.emit('move_snake', {'direction': 'left'})
        elif "right" in command:
            self.socketio.emit('move_snake', {'direction': 'right'})

        # Game control commands
        elif "start" in command or "begin" in command or "play" in command:
            self.socketio.emit('game_control', {'action': 'start'})
        elif "pause" in command or "stop" in command:
            self.socketio.emit('game_control', {'action': 'pause'})
        elif "restart" in command or "reset" in command:
            self.socketio.emit('game_control', {'action': 'restart'})
        elif "quit" in command or "exit" in command:
            self.socketio.emit('game_control', {'action': 'quit'})
            self.stop_listening()  # Stop listening when quitting the game
        elif "faster" in command or "speed up" in command:
            self.socketio.emit('game_control', {'action': 'increase_speed'})
        elif "slower" in command or "slow down" in command:
            self.socketio.emit('game_control', {'action': 'decrease_speed'})
        elif "mute" in command:
            self.socketio.emit('game_control', {'action': 'mute'})
        elif "unmute" in command or "sound on" in command:
            self.socketio.emit('game_control', {'action': 'unmute'})
        else:
            print(f"Command '{command}' not recognized as a valid game command")


# Example usage in a Flask app
def initialize_voice_controller(app):
    socketio = SocketIO(app)
    voice_controller = VoiceController(socketio)

    @socketio.on('connect')
    def handle_connect():
        print("Client connected")

    @socketio.on('start_voice_control')
    def handle_start_voice():
        success = voice_controller.start_listening()
        emit('voice_control_status', {'active': success})

    @socketio.on('stop_voice_control')
    def handle_stop_voice():
        success = voice_controller.stop_listening()
        emit('voice_control_status', {'active': not success})

    return socketio, voice_controller