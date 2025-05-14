import cv2
import numpy as np
import pyautogui
from flask_socketio import emit


def start_eye_tracking(socketio):
    """Start eye tracking for snake game control"""
    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    # Track previous eye position to detect movement
    prev_eye_x, prev_eye_y = 0, 0
    threshold = 5  # Sensitivity threshold

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Convert to grayscale for face/eye detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            # Region of interest for the face
            roi_gray = gray[y:y + h, x:x + w]
            roi_color = frame[y:y + h, x:x + w]

            # Detect eyes within the face region
            eyes = eye_cascade.detectMultiScale(roi_gray)

            if len(eyes) >= 2:  # If both eyes detected
                # Get the center point of each eye
                eye_centers = []
                for (ex, ey, ew, eh) in eyes:
                    eye_center_x = x + ex + ew // 2
                    eye_center_y = y + ey + eh // 2
                    eye_centers.append((eye_center_x, eye_center_y))
                    cv2.circle(frame, (eye_center_x, eye_center_y), 2, (0, 255, 0), -1)

                # Calculate the average eye position
                avg_eye_x = sum(center[0] for center in eye_centers) // len(eye_centers)
                avg_eye_y = sum(center[1] for center in eye_centers) // len(eye_centers)

                # Detect movement based on change in position
                dx = avg_eye_x - prev_eye_x
                dy = avg_eye_y - prev_eye_y

                # Determine direction based on movement
                if abs(dx) > threshold or abs(dy) > threshold:
                    if abs(dx) > abs(dy):  # More horizontal movement
                        if dx > threshold:
                            direction = "right"
                        elif dx < -threshold:
                            direction = "left"
                    else:  # More vertical movement
                        if dy > threshold:
                            direction = "down"
                        elif dy < -threshold:
                            direction = "up"

                    # Emit the direction to the client
                    socketio.emit('eye_command', {'direction': direction})

                # Update previous position
                prev_eye_x, prev_eye_y = avg_eye_x, avg_eye_y

        # Display the frame for debugging (can be disabled in production)
        cv2.imshow('Eye Tracking', frame)

        # Break loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release resources
    cap.release()
    cv2.destroyAllWindows()


def stop_eye_tracking():
    """Stop the eye tracking process"""
    cv2.destroyAllWindows()