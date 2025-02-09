# -*- coding: utf-8 -*-
# this is a service for FRC Robotics
# |--start--connectToI2C--openMainShell-->


from time import time, sleep
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

import subprocess
import threading
import queue


def read_stream(stream, output_queue):
    """非阻塞讀取流，並將數據放入佇列"""
    for line in iter(stream.readline, ''):
        output_queue.put(line)
    stream.close()

    
try:
    # Create an I2C interface
    serial = i2c(port=7, address=0x3C)
    # Create the OLED device instance
    device = ssd1306(serial)
    # Clear the display
    device.clear()
    # Create an image buffer to draw on
    width = device.width
    height = device.height
except Exception as e:
    print(e)

# open main process
process = subprocess.Popen(
    ['/bin/bash', '/home/jetson/main.sh'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1  # 行緩衝
)

stdout_queue = queue.Queue()
stderr_queue = queue.Queue()

stdout_thread = threading.Thread(target=read_stream,
args=(process.stdout, stdout_queue))
stderr_thread = threading.Thread(target=read_stream,
args=(process.stderr, stderr_queue))

stdout_thread.start()
stderr_thread.start()

num = 1
last_time = time()
move = 0
last_err = ""


out = ""
err = ""

# 主進程
try:
    while True:
        try:
            
            while True:
                image = Image.new('1', (width, height))
                draw = ImageDraw.Draw(image)
    
                # Load a font
                font = ImageFont.load_default()
    
                h = num // 3600
                m = (num % 3600) // 60  # Fixing the minute calculation
                s = num % 60
    
                # Draw the first line of text (time)
                draw.text((0, 0), f"ST:{str(h)}h {str(m)}m {str(s)}s",font=font, fill=255)
            
    
    
                # 處理標準輸出
                if not stdout_queue.empty():
                    out = stdout_queue.get_nowait()
    
                # 處理標準錯誤
                if not stderr_queue.empty():
                    err = stderr_queue.get_nowait()+"======================="
    
                # 檢查子進程是否結束
                is_ended = process.poll() is not None and stdout_queue.empty()and stderr_queue.empty()
    
                draw.text((80, 0), "ended" if is_ended else "running",font=font, fill=255)
    
    
    
                if out:
                    draw.text((0, 10), out, font=font, fill=255)
                if err:
                    if err != last_err or move <= 0:
                        last_err = err
                        move = len(last_err)-28
                    if len(err.replace('\n', ' ')) > 28:
                        draw.text((0, 20), err.replace('\n','')[-28-move:-1-move], font=font, fill=255)
                        if move-2 < 0:
                            move = 0
                        else:
                            move -= 5
                    else:
                        draw.text((0, 20), err.replace('\n', '')[-30:-1],font=font, fill=255)
            
                ipaddr = subprocess.run("ip -br addr show eno1 | grep -oP '\\d{1,3}(\\.\\d{1,3}){3}/\\d{1,2}'", shell=True, capture_output=True, text=True)
        
                is_web = subprocess.run("sudo systemctl status web.service | grep -oE 'active|inactive|failed'", shell=True, capture_output=True, text=True)
        
                draw.text((0, 30), "ip :  "+str(ipaddr.stdout).replace('\n', '').replace('/', '   / '), font=font, fill=255)
                draw.text((0, 40), "WebServerState "+str(is_web.stdout).replace('\n', ''), font=font, fill=255)
    
    
                # Display the image
                device.display(image)
                num += 1
                dt = time() - last_time
                if dt<1:
                    sleep(1-dt)
                else:
                    print(f"time over : {dt}")
                last_time = time()
        except Exception as e:
            print(e)
            try:
                if 'serial' in locals():
                    serial.cleanup()  # 關閉 I2C 接口
            except Exception as cleanup_error:
                print(f"Error serial cleanup: {cleanup_error}")
            try:
                if 'device' in locals():
                    device.cleanup()  # 清除螢幕
            except Exception as cleanup_error:
                print(f"Error device cleanup: {cleanup_error}")
            try:
                # Create an I2C interface
                serial = i2c(port=7, address=0x3C)
                # Create the OLED device instance
                device = ssd1306(serial)
                # Clear the display
                device.clear()
                # Create an image buffer to draw on
                width = device.width
                height = device.height
            except Exception as e:
                print(e)
            print("connected")
            sleep(1)


finally:
    # 確保資源釋放
    stdout_thread.join()
    stderr_thread.join()
    process.stdout.close()
    process.stderr.close()



