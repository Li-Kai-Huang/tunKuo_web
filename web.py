# -*- coding: utf-8 -*-

#======================================
#=============== IMPORT ===============
#======================================

from flask import Flask, request, render_template, Response, jsonify, send_from_directory,redirect
from subprocess import run
import threading
import cv2
from jtop import jtop
from time import sleep
from cscore import CameraServer
from ntcore import NetworkTableInstance
import json
import os

#====================================
#=============== INIT ===============
#====================================

info = None

app = Flask(__name__)

# File paths
MAIN_PY_PATH = '/home/jetson/main.py'
MAIN_SH_PATH = '/home/jetson/main.sh'
CONFIG_DEFAULT_PATH = '/opt/default_config.json'
CONFIG_PATH = '/opt/config.json'
WEB_HTML_PATH = 'web.html'
DOWNLOAD_FOLDER = '/'
UPLOAD_FOLDER = '/home/jetson'
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#===================================
#=============== WEB ===============
#===================================

@app.before_request
def enforce_http():
    # 檢查是否是 HTTPS 請求
    if request.is_secure:
        # 如果是 HTTPS 請求，重定向到 HTTP
        return redirect(request.url.replace("https://", "http://"), code=301)


def get_info():
    return info

def info_update():
    global info
    while True:
        try:
            with jtop() as jetson:
                # jetson.ok() will provide the proper update frequency
                while True:
                    if jetson.ok():
                        # 讀取統計資訊
                        info = jetson.stats
                    sleep(0.5)
        except Exception as e:
            print(e)


@app.route('/', methods=['GET'])
def index():
    return render_template(WEB_HTML_PATH)

@app.route('/favicon.png')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'templates/favicon.png', mimetype='image/png')

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
                run(['sudo', 'shutdown', '-h', 'now'])
                return jsonify({"status": "success", "message": "Shutting down the system"}), 200
            elif command == 'reboot':
                run(['sudo', 'reboot'])
                return jsonify({"status": "success", "message": "Rebooting the system"}), 200
            elif command == 'restart_web_service':
                run(['sudo', 'systemctl', 'restart', 'web.service'])
                return jsonify({"status": "success", "message": "Service restarted"}), 200
            elif command == 'restart_maind_service':
                run(['sudo', 'systemctl', 'restart', 'maind.service'])
                return jsonify({"status": "success", "message": "Service restarted"}), 200
            else:
                return jsonify({"status": "error", "message": "Unknown command"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/cameras', methods=['GET', 'POST'])
def cameras():
    if request.method == 'GET':
        try:
            command = request.args.get('command', ' ').strip().lower()
            
            if command == 'config':
                
                config = load_settings(CONFIG_PATH)
                
                return app.response_class(
                        response=json.dumps({"status": "success", "data": config}, indent=4, sort_keys=True, default=str),
                        status=200,
                        mimetype='application/json'
                    )

            elif command == 'cameras':
                return jsonify({"status": "error", "message": "Unknown command"}), 400

            else:
                return jsonify({"status": "error", "message": "Unknown command"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    if request.method == 'POST':

        try:
            data = request.get_json()

            command = data.get('command', '').lower()

            if command == 'replace':
                run(['sudo', 'cp', CONFIG_DEFAULT_PATH, CONFIG_PATH])
                return jsonify({"status": "success", "message": "replaced config"}), 200

            if command == 'setting':

                data = data.get('data', '')

                if not data:
                    return jsonify({"status": "error", "message": "缺少檔案內容"}), 400

                # 儲存檔案內容
                try:
                    save_settings(data, CONFIG_PATH)

                    return jsonify({"status": "success", "message": f"檔案儲存成功"}), 200
                except Exception as e:
                    return jsonify({"status": "error", "message": str(e)}), 500

            else:
                    return jsonify({"status": "error", "message": "Unknown command"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/files', methods=['GET', 'POST'])
def files():
    if request.method == 'POST':
        # 檢查是否有檔案
        if 'file' in request.files:
            # 檔案上傳
            file = request.files['file']
            if file.filename == '':
                return jsonify({"status": "error", "message": "No selected file"}), 400
            filename = request.form.get("filename") if request.form.get("filename") else file.filename

            # 儲存檔案
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                return jsonify({"status": "success", "message": f"檔案 {filename} 儲存成功"}), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        elif 'filename' in request.form and 'content' in request.files:
            # 編輯檔案內容
            filename = request.form.get('filename')
            content_file = request.files['content']

            if not filename:
                return jsonify({"status": "error", "message": "缺少檔案名稱"}), 400
            if not content_file:
                return jsonify({"status": "error", "message": "缺少檔案內容"}), 400

            # 儲存檔案內容
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                with open(file_path, 'wb') as f:
                    f.write(content_file.read())  # 儲存傳送的檔案內容

                return jsonify({"status": "success", "message": f"檔案 {filename} 儲存成功"}), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        else:
            return jsonify({"status": "error", "message": "未知的請求"}), 400


    if request.method == 'GET':
        path = request.args.get('path', ' ').strip()
        download = request.args.get('download', '').strip()
        full_path = os.path.join(app.config['DOWNLOAD_FOLDER'], path)

        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": "Path does not exist"}), 400

        if download.lower() == 'true':
            return send_from_directory(app.config['DOWNLOAD_FOLDER'], path, as_attachment=True)
        elif download.lower() == 'false':
            return send_from_directory(app.config['DOWNLOAD_FOLDER'], path, as_attachment=False)


        files_list = os.listdir(full_path)
        files_info = []
        for file in files_list:
            file_path = os.path.join(full_path, file)
            files_info.append({
                "name": file,
                "isDirectory": os.path.isdir(file_path)
            })
        return jsonify(files_info)

#@app.route('/img', methods=['GET'])
#def img():
#    # Serve MJPEG stream using the generate_frames function
#    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

#======================================
#=============== CAMERA ===============
#======================================


def get_camera_settings(device):
    """ 使用 v4l2-ctl 獲取所有相機控制參數，包含 min, max, default, current """
    result = run(
        ["v4l2-ctl", "-d", device, "--list-ctrls"],
        capture_output=True, text=True
    )

    settings = {}
    for line in result.stdout.split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        name = parts[0][:-1]  # 參數名稱 (移除冒號)
        values = {part.split('=')[0]: int(part.split('=')[1]) for part in parts[1:] if '=' in part}
        settings[name] = values

    return settings

def save_settings(settings, filename):
    """ 將相機設定存為 JSON """
    with open(filename, "w") as f:
        json.dump(settings, f, indent=4)
    print(f"[INFO] 相機設定已儲存至 {filename}")

def load_settings(filename):
    """ 載入 JSON 設定 """
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return None


def start_CameraServer(config):
    """ 啟動 cscore 影像串流 """
    print(f"[Info] 啟動 CS with {config}")
    for key in config.keys():
        if config[key]["enabled"]:
            
            print(f"[INFO] Camera enabled {config[key]}")
            cs = CameraServer.startAutomaticCapture(name=config[key]["name"], path=config[key]["path"])
            if len(config[key]["settings"].keys()) == 0:
                config[key]["settings"].update(json.loads(cs.getConfigJson()))
                save_settings(config, CONFIG_PATH)
                
            cs.setConfigJson(config[key]["settings"])

#====================================
#=============== MAIN ===============
#====================================

if __name__ == '__main__':
    try:
        config = load_settings(CONFIG_PATH)
        if config is None:
            print("[Error] 無法取得相機設定")
        else:
            start_CameraServer(config)
    except Exception as e:
        print(f"[Error] CS 啟動失敗 : {str(e)}")

    # Start the Flask application
    updataT = threading.Thread(target=info_update)
    updataT.start()
    app.run(host='0.0.0.0', port=5801, threaded=True)
