import cv2
import numpy as np
import threading
import time
from flask_socketio import emit

# Global variables
eye_tracking_active = False
eye_tracking_thread = None
calibration_complete = False
calibration_points = {"center": None, "left": None, "right": None, "up": None, "down": None}
current_direction = "right"  # Default starting direction
stability_threshold = 3  # Number of consecutive detections needed to change direction
direction_counts = {"left": 0, "right": 0, "up": 0, "down": 0}


def detect_eyes(frame):
    """Detect eyes in the given frame"""
    # Convert to grayscale for faster processing
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Load pre-trained Haar Cascade for eye detection
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    # Detect eyes
    eyes = eye_cascade.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(30, 30),
    )

    return eyes


def get_pupil_position(eye_frame):
    """Detect pupil in the eye frame and return its position"""
    # Convert to grayscale and apply blur
    gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (7, 7), 0)

    # Use adaptive thresholding to find the pupil (dark part)
    _, threshold = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Get the largest contour (likely to be the pupil)
    pupil_contour = max(contours, key=cv2.contourArea)

    # Get centroid of the pupil
    M = cv2.moments(pupil_contour)
    if M["m00"] == 0:
        return None

    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])

    # Add to smoothing window
    pupil_positions.append((cx, cy))
    if len(pupil_positions) > smoothing_window:
        pupil_positions.pop(0)

    # Calculate smoothed position
    if len(pupil_positions) > 0:
        avg_x = sum(p[0] for p in pupil_positions) / len(pupil_positions)
        avg_y = sum(p[1] for p in pupil_positions) / len(pupil_positions)
        return (int(avg_x), int(avg_y))

    return (cx, cy)


def determine_direction(pupil_position, eye_frame):
    """Determine looking direction based on pupil position and calibration"""
    global calibration_points

    if not calibration_complete or pupil_position is None:
        return None

    # Get eye frame dimensions
    height, width = eye_frame.shape[:2]
    center_x, center_y = width // 2, height // 2

    # Calculate the offset from center
    x, y = pupil_position
    offset_x = x - center_x
    offset_y = y - center_y

    # Calculate thresholds based on calibration
    x_threshold = width * 0.15  # 15% of width
    y_threshold = height * 0.15  # 15% of height

    # Add hysteresis to prevent rapid direction changes
    if abs(offset_x) > abs(offset_y):
        if offset_x < -x_threshold * 1.2:  # 20% more threshold for left
            return "left"
        elif offset_x > x_threshold * 1.2:  # 20% more threshold for right
            return "right"
    else:
        if offset_y < -y_threshold * 1.2:  # 20% more threshold for up
            return "up"
        elif offset_y > y_threshold * 1.2:  # 20% more threshold for down
            return "down"

    return None


def calibrate(socketio):
    """Begin calibration process for eye tracking"""
    global calibration_points, calibration_complete

    # Reset calibration
    calibration_points = {"center": None, "left": None, "right": None, "up": None, "down": None}
    calibration_complete = False

    # Start webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        socketio.emit('eye_status', {'message': 'Error: Could not open webcam'})
        return False

    # Calibration sequence
    calibration_sequence = ["center", "left", "right", "up", "down"]
    for position in calibration_sequence:
        # Tell user what to look at
        socketio.emit('eye_calibration', {'position': position, 'message': f'Look {position}'})

        # Give user time to look there
        time.sleep(2)

        # Capture frame
        ret, frame = cap.read()
        if not ret:
            cap.release()
            socketio.emit('eye_status', {'message': 'Error during calibration'})
            return False

        # Detect eyes
        eyes = detect_eyes(frame)
        if len(eyes) == 0:
            socketio.emit('eye_status', {'message': 'No eyes detected, please try again'})
            continue

        # Process the first detected eye
        x, y, w, h = eyes[0]
        eye_frame = frame[y:y + h, x:x + w]

        # Get pupil position for this calibration point
        pupil_pos = get_pupil_position(eye_frame)
        if pupil_pos:
            calibration_points[position] = pupil_pos
            socketio.emit('eye_calibration', {'position': position, 'status': 'complete'})
        else:
            socketio.emit('eye_status', {'message': f'Could not detect pupil when looking {position}'})

    # Check if all points were calibrated
    if all(calibration_points.values()):
        calibration_complete = True
        socketio.emit('eye_status', {'message': 'Calibration complete! You can now control with your eyes.'})
        cap.release()
        return True
    else:
        socketio.emit('eye_status', {'message': 'Calibration incomplete, please try again'})
        cap.release()
        return False


def eye_tracking_loop(socketio):
    """Main eye tracking loop that runs in a thread"""
    global eye_tracking_active, current_direction, direction_counts

    # Start webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        socketio.emit('eye_status', {'message': 'Error: Could not open webcam'})
        eye_tracking_active = False
        return

    socketio.emit('eye_status', {'message': 'Eye tracking active'})

    try:
        while eye_tracking_active:
            # Capture frame
            ret, frame = cap.read()
            if not ret:
                continue

            # Detect eyes
            eyes = detect_eyes(frame)
            if len(eyes) == 0:
                socketio.emit('eye_status', {'message': 'No eyes detected'})
                continue

            # Process the first detected eye
            x, y, w, h = eyes[0]
            eye_frame = frame[y:y + h, x:x + w]

            # Get pupil position
            pupil_pos = get_pupil_position(eye_frame)
            if not pupil_pos:
                continue

            # Determine direction from pupil position
            direction = determine_direction(pupil_pos, eye_frame)

            # Apply stability checks to prevent accidental direction changes
            if direction:
                # Increment counter for detected direction
                direction_counts[direction] += 1

                # Reset counters for all other directions
                for d in ["left", "right", "up", "down"]:
                    if d != direction:
                        direction_counts[d] = 0

                # If we have enough consecutive detections, change direction
                if direction_counts[direction] >= stability_threshold:
                    if direction != current_direction:
                        # Only change direction if it's a valid move (not 180 degrees)
                        valid_change = True
                        if (direction == "left" and current_direction == "right") or \
                                (direction == "right" and current_direction == "left") or \
                                (direction == "up" and current_direction == "down") or \
                                (direction == "down" and current_direction == "up"):
                            valid_change = False

                        if valid_change:
                            current_direction = direction
                            socketio.emit('eye_command', {'direction': direction})
                            # Reset counters after direction change
                            for d in direction_counts:
                                direction_counts[d] = 0

            # Short delay to prevent CPU overload
            time.sleep(0.05)  # Reduced delay for more responsive tracking

    except Exception as e:
        print(f"Error in eye tracking loop: {e}")
    finally:
        cap.release()
        socketio.emit('eye_status', {'message': 'Eye tracking stopped'})


def start_eye_tracking(socketio):
    """Start eye tracking in a separate thread"""
    global eye_tracking_active, eye_tracking_thread

    if eye_tracking_active:
        return False  # Already running

    # Check if calibration has been done
    if not calibration_complete:
        socketio.emit('eye_status', {'message': 'Please calibrate first'})
        return False

    eye_tracking_active = True
    eye_tracking_thread = threading.Thread(target=eye_tracking_loop, args=(socketio,))
    eye_tracking_thread.daemon = True
    eye_tracking_thread.start()

    return True


def stop_eye_tracking():
    """Stop eye tracking"""
    global eye_tracking_active

    if not eye_tracking_active:
        return False

    eye_tracking_active = False
    return True