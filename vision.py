# -*- coding: utf-8 -*-
import time
import queue
import csv  # 新增：用于记录实验数据
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from util import (
    is_finger_bend, get_gesture_onehand,
    img_width, img_height, FlyCommand, GestureOneHand
)

GESTURE_MAP = {
    GestureOneHand.OK: FlyCommand.TAKE_OFF, GestureOneHand.FIVE: FlyCommand.LAND,
    GestureOneHand.ONE: FlyCommand.MOVE_FORWARD, GestureOneHand.TWO: FlyCommand.MOVE_BACKWARD,
    GestureOneHand.THREE: FlyCommand.MOVE_LEFT, GestureOneHand.FOUR: FlyCommand.MOVE_RIGHT,
    GestureOneHand.SIX: FlyCommand.MOVE_UP, GestureOneHand.SEVEN: FlyCommand.MOVE_DOWN,
    GestureOneHand.GOOD: FlyCommand.YOW_LEFT, GestureOneHand.BAD: FlyCommand.YOW_RIGHT,
    GestureOneHand.NONE: FlyCommand.NONE
}

def vision_process(command_queue):
    from picamera2 import Picamera2
    from libcamera import Transform
    
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(
        main={"format": 'RGB888', "size": (img_width, img_height)}, 
        transform=Transform(vflip=True, hflip=True)))
    picam2.start()

    model_path = '/home/kexiaopang/Desktop/model/hand_landmarker.task'
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1)
    detector = vision.HandLandmarker.create_from_options(options)
    
    HISTORY_LEN = 12
    gest_history = [GestureOneHand.NONE] * HISTORY_LEN 
    prev_time = 0

    print("[Vision] 实验数据记录模式已开启。数据将保存至 experiment_data.csv")

    # 创建 CSV 文件并写入表头
    with open('experiment_data.csv', mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Raw_Gesture_Value', 'Filtered_Gesture_Value'])

        start_experiment_time = time.time()

        while True:
            curr_time = time.time() - start_experiment_time
            img_RGB = picam2.capture_array()
            img_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_RGB)
            detection_result = detector.detect(img_mp)
            
            # 1. 获取原始信号 (Raw Signal)
            raw_gest = GestureOneHand.NONE
            if detection_result.hand_landmarks:
                landmarks = detection_result.hand_landmarks[0]
                raw_gest = get_gesture_onehand(landmarks, is_finger_bend(landmarks))

            # 2. 滤波逻辑信号 (Filtered Signal)
            gest_history.pop(0)
            gest_history.append(raw_gest)
            most_common_gest = max(set(gest_history), key=gest_history.count)
            stable_gest = most_common_gest if gest_history.count(most_common_gest) >= 10 else GestureOneHand.NONE
            
            # 3. 将手势枚举转换为数字（方便绘图，如 MOVE_FORWARD=1, NONE=0）
            raw_val = 1 if raw_gest == GestureOneHand.ONE else 0
            filtered_val = 1 if stable_gest == GestureOneHand.ONE else 0
            
            # 写入 CSV
            writer.writerow([round(curr_time, 3), raw_val, filtered_val])

            # 指令下发给蓝牙进程（保持正常控制）
            stable_cmd = GESTURE_MAP.get(stable_gest, FlyCommand.NONE)
            if command_queue.full():
                try: command_queue.get_nowait()
                except: pass
            command_queue.put(stable_cmd)
            
            # 限制采集频率，防止 CSV 过大
            time.sleep(0.01)