# -*- coding: utf-8 -*-
import numpy as np
import math
from enum import Enum, auto
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2

# 系统控制状态机枚举
class GestureOneHand(Enum):
    NONE = auto(); ONE = auto(); TWO = auto(); THREE = auto(); FOUR = auto()
    FIVE = auto(); SIX = auto(); SEVEN = auto(); EIGHT = auto(); OK = auto()
    GOOD = auto(); BAD = auto()

class FlyCommand(Enum):
    NONE = auto(); TAKE_OFF = auto(); LAND = auto()
    MOVE_RIGHT = auto(); MOVE_LEFT = auto(); MOVE_FORWARD = auto(); MOVE_BACKWARD = auto()
    MOVE_UP = auto(); MOVE_DOWN = auto(); YOW_LEFT = auto(); YOW_RIGHT = auto()

img_width = 720
img_height = 640 

def points_distance(A, B):
    """计算两像素点间的欧氏距离"""
    return math.sqrt(((A.x - B.x) * img_width) ** 2 + ((A.y - B.y) * img_height) ** 2)

def is_point_in_polygon(hand_landmarks, point_index):
    """基于射线交叉法判定指尖坐标是否内含于掌心拓扑多边形"""
    polygon_indices = [0, 1, 2, 3, 6, 10, 14, 19, 18, 17, 0]
    point = hand_landmarks[point_index]
    px, py = int(point.x * img_width), int(point.y * img_height)
    polygon = [(int(hand_landmarks[i].x * img_width), int(hand_landmarks[i].y * img_height)) for i in polygon_indices]
    num_intersections = 0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]; x2, y2 = polygon[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x_intersection = (py - y1) * (x2 - x1) / (y2 - y1) + x1
            if x_intersection > px: num_intersections += 1
    return num_intersections % 2 == 1

def is_finger_bend(hand_landmarks):
    """提取手指屈伸特征向量"""
    point_list = [4, 8, 12, 16, 20]
    return [0 if is_point_in_polygon(hand_landmarks, p) else 1 for p in point_list]

def get_gesture_onehand(hand_landmarks, finger_state):
    """手势模式识别逻辑"""
    palm_size = points_distance(hand_landmarks[0], hand_landmarks[9]) + 1e-6
    dist_4_8 = points_distance(hand_landmarks[4], hand_landmarks[8]) / palm_size
    is_middle_up = hand_landmarks[12].y < hand_landmarks[10].y
    is_ring_up = hand_landmarks[16].y < hand_landmarks[14].y
    is_pinky_up = hand_landmarks[20].y < hand_landmarks[18].y

    if dist_4_8 < 0.45:
        return GestureOneHand.OK if (is_middle_up and is_ring_up and is_pinky_up) else GestureOneHand.SEVEN
    
    if finger_state[0] == 1 and sum(finger_state[1:]) == 0:
        return GestureOneHand.GOOD if hand_landmarks[4].y < hand_landmarks[2].y else GestureOneHand.BAD
    
    mapping = {
        (0, 1, 0, 0, 0): GestureOneHand.ONE, (0, 1, 1, 0, 0): GestureOneHand.TWO,
        (0, 1, 1, 1, 0): GestureOneHand.THREE, (0, 1, 1, 1, 1): GestureOneHand.FOUR,
        (1, 1, 1, 1, 1): GestureOneHand.FIVE, (1, 0, 0, 0, 1): GestureOneHand.SIX,
        (1, 1, 0, 0, 0): GestureOneHand.EIGHT
    }
    return mapping.get(tuple(finger_state), GestureOneHand.NONE)

def draw_landmarks_on_image(rgb_image, detection_result):
    """生成骨架拓扑可视化反馈图"""
    annotated_image = np.copy(rgb_image)
    if not detection_result.hand_landmarks: return annotated_image
    for hand_landmarks in detection_result.hand_landmarks:
        hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
        hand_landmarks_proto.landmark.extend([
            landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in hand_landmarks
        ])
        solutions.drawing_utils.draw_landmarks(
            annotated_image, hand_landmarks_proto, solutions.hands.HAND_CONNECTIONS,
            solutions.drawing_styles.get_default_hand_landmarks_style(),
            solutions.drawing_styles.get_default_hand_connections_style())
    return annotated_image