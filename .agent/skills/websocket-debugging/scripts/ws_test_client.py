#!/usr/bin/env python3
"""
WebSocket 测试客户端

用于测试 /ws/realtime 端点的 WebSocket 连接和消息传输。
"""

import asyncio
import json
import base64
import argparse
from typing import Optional
import websockets
from websockets.client import WebSocketClientProtocol


async def send_audio_chunk(websocket: WebSocketClientProtocol, audio_data: bytes):
    """发送音频数据块"""
    message = {
        "type": "audio",
        "data": {
            "audio": base64.b64encode(audio_data).decode('utf-8'),
            "sample_rate": 16000,
            "channels": 1
        }
    }
    await websocket.send(json.dumps(message))
    print(f"✓ 发送音频数据: {len(audio_data)} bytes")


async def receive_messages(websocket: WebSocketClientProtocol):
    """接收服务器消息"""
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "transcript":
                text = data["data"]["text"]
                is_final = data["data"].get("is_final", False)
                confidence = data["data"].get("confidence", 0)
                print(f"📝 转写: {text} (final={is_final}, confidence={confidence:.2f})")
            
            elif msg_type == "response":
                response_text = data["data"]["text"]
                print(f"🤖 AI 响应: {response_text}")
            
            elif msg_type == "error":
                error_msg = data["data"]["message"]
                print(f"❌ 错误: {error_msg}")
            
            else:
                print(f"📨 收到消息: {data}")
    
    except websockets.exceptions.ConnectionClosed:
        print("⚠️ 连接已关闭")


async def test_websocket(url: str, duration: int = 10):
    """测试 WebSocket 连接"""
    print(f"🔌 连接到: {url}")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✓ 连接成功!")
            
            # 启动消息接收任务
            receive_task = asyncio.create_task(receive_messages(websocket))
            
            # 模拟发送音频数据
            for i in range(duration):
                # 生成模拟音频数据 (静音)
                audio_chunk = b'\x00' * 3200  # 100ms @ 16kHz, 16-bit PCM
                await send_audio_chunk(websocket, audio_chunk)
                await asyncio.sleep(0.1)  # 100ms 间隔
            
            # 等待接收任务完成
            await asyncio.sleep(2)
            receive_task.cancel()
            
            print("✓ 测试完成")
    
    except Exception as e:
        print(f"❌ 连接失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="WebSocket 测试客户端")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000/ws/realtime",
        help="WebSocket URL (默认: ws://localhost:8000/ws/realtime)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="测试持续时间(秒) (默认: 10)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("WebSocket 测试客户端")
    print("=" * 60)
    
    asyncio.run(test_websocket(args.url, args.duration))


if __name__ == "__main__":
    main()
