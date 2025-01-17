from flask import Flask, request, render_template, Response, jsonify
import subprocess
import threading
import cv2
from jtop import jtop
from time import sleep
import json

info = None

app = Flask(__name__)

# File paths
MAIN_PY_PATH = '/home/jetson/main.py'
MAIN_SH_PATH = '/home/jetson/main.sh'
WEB_HTML_PATH = 'web.html'

# Initialize the camera
cap = cv2.VideoCapture(0)

# Ensure the camera is opened
if not cap.isOpened():
    print("Error: Camera not found!")
    exit()

def get_info():
    return info

def info_update():
    with jtop() as jetson:
    # jetson.ok() will provide the proper update frequency
    while True:
        if jetson.ok():
            # 讀取統計資訊
            info = jetson.stats
        sleep(0.5)


def generate_frames():
    while True:
        # Capture a frame from the camera
        ret, frame = cap.read()

        if not ret:
            print("Error: Failed to capture frame!")
            break

        frame = cv2.resize(frame, (160, 120))

        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            print("Error: Failed to encode frame!")
            break

        # Convert the frame to bytes
        frame = buffer.tobytes()

        # Send the frame to the client
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        sleep(0.03)

@app.route('/', methods=['GET'])
def index():
    return render_template(WEB_HTML_PATH)

@app.route('/panel', methods=['GET', 'POST'])
def panel():
    if request.method == 'GET':
        try:
            return app.response_class(
                    response=json.dumps({"status": "success", "data": get_info()}, indent=4, sort_keys=True, default=str),
                    status=200,
                    mimetype='application/json'
                )
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    if request.method == 'POST':

        try:
            
            data = request.get_json()

            command = data.get('command', '').lower()

            if command == 'shutdown':
                subprocess.run(['sudo', 'shutdown', '-h', 'now'])
                return jsonify({"status": "success", "message": "Shutting down the system"}), 200
            elif command == 'reboot':
                subprocess.run(['sudo', 'reboot'])
                return jsonify({"status": "success", "message": "Rebooting the system"}), 200
            elif command == 'restart_service':
                subprocess.run(['sudo', 'systemctl', 'restart', 'oled_server.service'])
                return jsonify({"status": "success", "message": "Service restarted"}), 200
            else:
                return jsonify({"status": "error", "message": "Unknown command"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/cameras', methods=['GET', 'POST'])
def cameras():
    if request.method == 'POST':
        return

@app.route('/files', methods=['GET', 'POST'])
def files():
    if request.method == 'POST':
        return

@app.route('/img', methods=['GET'])
def img():
    # Serve MJPEG stream using the generate_frames function
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Start the Flask application
    thread.start_new_thread(, ("Thread-1", 2, ) )
    app.run(host='0.0.0.0', port=5000, threaded=True)

