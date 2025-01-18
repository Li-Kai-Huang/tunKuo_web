from flask import Flask, request, render_template, Response, jsonify, send_from_directory,redirect
import subprocess
import threading
import cv2
from jtop import jtop
from time import sleep
import json
import os

info = None

app = Flask(__name__)

# File paths
MAIN_PY_PATH = '/home/jetson/main.py'
MAIN_SH_PATH = '/home/jetson/main.sh'
WEB_HTML_PATH = 'web.html'
DOWNLOAD_FOLDER = '/'  # 替換為你想要保存文件的目錄
UPLOAD_FOLDER = '/home/jetson'
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize the camera
cap = cv2.VideoCapture(0)

@app.before_request
def enforce_http():
    # 檢查是否是 HTTPS 請求
    if request.is_secure:
        # 如果是 HTTPS 請求，重定向到 HTTP
        return redirect(request.url.replace("https://", "http://"), code=301)

# Ensure the camera is opened
if not cap.isOpened():
    print("Error: Camera not found!")
    exit()

def get_info():
    return info

def info_update():
    global info
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
        # 處理 POST 請求，上傳檔案
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({"status": "success", "message": "File uploaded successfully"}), 200

    # 處理 GET 請求，列出或顯示檔案內容
    if request.method == 'GET':
        path = request.args.get('path', '').strip()
        download = request.args.get('download', '').strip()

        if not path:
            return jsonify({"status": "error", "message": "Path is required"}), 400
        
        full_path = os.path.join(app.config['DOWNLOAD_FOLDER'], path)

        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": "File does not exist"}), 404

        # 如果需要下載文件
        if download:
            return send_from_directory(app.config['DOWNLOAD_FOLDER'], path, as_attachment=True)

        # 如果是文本檔案，返回檔案內容
        if path.endswith(('.py', '.sh')):
            with open(full_path, 'r') as f:
                content = f.read()
            return jsonify({"status": "success", "content": content}), 200

        # 列出目錄內容
        files_list = os.listdir(full_path)
        files_info = []
        for file in files_list:
            file_path = os.path.join(full_path, file)
            files_info.append({
                "name": file,
                "isDirectory": os.path.isdir(file_path)
            })
        return jsonify(files_info)

    # 如果是 POST 請求來保存檔案內容
    elif request.method == 'POST':
        data = request.get_json()
        path = data.get('path', '').strip()
        content = data.get('content', '').strip()

        if not path:
            return jsonify({"status": "error", "message": "Path is required"}), 400
        
        full_path = os.path.join(app.config['DOWNLOAD_FOLDER'], path)

        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": "File does not exist"}), 404

        # 只允許編輯 .txt 和 .sh 檔案
        if not path.endswith(('.txt', '.sh')):
            return jsonify({"status": "error", "message": "File type not editable"}), 400

        # 保存編輯後的內容
        with open(full_path, 'w') as f:
            f.write(content)

        return jsonify({"status": "success", "message": "File edited successfully"}), 200

@app.route('/img', methods=['GET'])
def img():
    # Serve MJPEG stream using the generate_frames function
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Start the Flask application
    updataT = threading.Thread(target=info_update)
    updataT.start()
    app.run(host='0.0.0.0', port=5000, threaded=True)

