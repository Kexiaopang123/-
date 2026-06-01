# -*- coding: utf-8 -*-
from util import FlyCommand
import queue
import asyncio
from bleak import BleakScanner, BleakClient

TARGET_NAME = "pyDrone"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

def build_packet(cmd):
    pkt = bytearray([0x00, 127, 127, 127, 127, 0x00, 0x00, 0x00])
    if cmd == FlyCommand.TAKE_OFF: pkt[5] = 24
    elif cmd == FlyCommand.LAND: pkt[5] = 72
    elif cmd == FlyCommand.MOVE_FORWARD: pkt[2] = 185
    elif cmd == FlyCommand.MOVE_BACKWARD: pkt[2] = 70 
    elif cmd == FlyCommand.MOVE_LEFT: pkt[1] = 70 
    elif cmd == FlyCommand.MOVE_RIGHT: pkt[1] = 185
    elif cmd == FlyCommand.MOVE_UP: pkt[4] = 185
    elif cmd == FlyCommand.MOVE_DOWN: pkt[4] = 70 
    elif cmd == FlyCommand.YOW_LEFT: pkt[3] = 70 
    elif cmd == FlyCommand.YOW_RIGHT: pkt[3] = 185
    return pkt

async def robust_scan():
    print("[BLE] 正在扫描设备...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if (d.name or "Unknown") == TARGET_NAME:
            return d
    return None

async def ble_flight_loop(command_queue):
    while True:
        device = await robust_scan()
        if not device:
            print("[BLE] 未发现设备，重试中...")
            continue

        print(f"[BLE] 发现设备: {device.address}. 正在连接...")
        
        try:
            async with BleakClient(device, timeout=15.0) as client:
                print("[BLE] ✅ 连接成功！已部署长按防抖与连发机制。")
                
                last_received_cmd = FlyCommand.NONE
                last_executed_macro = FlyCommand.NONE
                
                while True:
                    if not client.is_connected:
                        print("\n[BLE Warning] 无人机物理连接断开.")
                        break 
                        
                    try:
                        new_cmd = command_queue.get_nowait()
                    except queue.Empty:
                        new_cmd = last_received_cmd
                        
                    last_received_cmd = new_cmd
                    cmd_to_send = new_cmd
                    
                    if new_cmd in [FlyCommand.TAKE_OFF, FlyCommand.LAND]:
                        if new_cmd != last_executed_macro:
                            print(f"[TX] 动作触发: {new_cmd.name} (连发破防抖)")
                            
                            # 1. 连发 5 枪（持续 0.5 秒），模拟真实人类按压，打穿飞控按键防抖
                            for _ in range(5):
                                if client.is_connected:
                                    await client.write_gatt_char(UART_RX_CHAR_UUID, build_packet(new_cmd), response=False)
                                await asyncio.sleep(0.1)
                                
                            last_executed_macro = new_cmd
                            
                            # 2. 按键松开，进入 2 秒的悬停保活等待期，让无人机做物理动作
                            print("[TX] 按键释放，平缓保活...")
                            for _ in range(20): 
                                await asyncio.sleep(0.1)
                                if client.is_connected:
                                    await client.write_gatt_char(UART_RX_CHAR_UUID, build_packet(FlyCommand.NONE), response=False)
                            
                            # 3. 清理废弃手势
                            while not command_queue.empty():
                                try: command_queue.get_nowait()
                                except queue.Empty: break
                            print("[TX] 动作保护期结束。")
                            continue
                        else:
                            cmd_to_send = FlyCommand.NONE
                    else:
                        if new_cmd != FlyCommand.NONE and new_cmd != last_executed_macro:
                            print(f"[TX] 姿态控制: {new_cmd.name}")
                        last_executed_macro = FlyCommand.NONE

                    # 常规时段保持 10Hz 平稳发送
                    if client.is_connected:
                        await client.write_gatt_char(UART_RX_CHAR_UUID, build_packet(cmd_to_send), response=False)
                    
                    await asyncio.sleep(0.1) 
                    
        except Exception as e:
            print(f"[BLE 异常] {repr(e)}")
            await asyncio.sleep(2.0)

def fly_process(command_queue):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_debug(False) 
    try:
        loop.run_until_complete(ble_flight_loop(command_queue))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()