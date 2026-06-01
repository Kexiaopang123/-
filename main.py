# -*- coding: utf-8 -*-
import multiprocessing
from vision import vision_process
from fly import fly_process

def main():
    # 使用多进程队列，仅传输极小的数据包（枚举指令），彻底消除 IPC 延迟
    command_queue = multiprocessing.Queue(maxsize=3)

    # 声明两个完全独立的系统进程
    # Process 1: 视觉感知与 UI 渲染引擎 (高 CPU 负载)
    p_vision = multiprocessing.Process(target=vision_process, args=(command_queue,), daemon=True)
    # Process 2: 低功耗蓝牙射频通信引擎 (高 I/O 敏感)
    p_fly = multiprocessing.Process(target=fly_process, args=(command_queue,), daemon=True)

    print("[Kernel] Initializing Multi-Processing Architecture...")
    p_vision.start()
    p_fly.start()

    try:
        # 主进程阻塞守候，管理子进程生命周期
        p_vision.join()
        p_fly.join()
    except KeyboardInterrupt:
        print("\n[Kernel] System termination signal received.")
        p_vision.terminate()
        p_fly.terminate()
        print("[Kernel] Safely shut down all processes.")

if __name__ == "__main__":
    main()