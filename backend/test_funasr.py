"""
FunASR WebSocket 连接测试脚本
"""
import asyncio
import websockets

FUNASR_URL = "ws://117.72.92.10:8889"

async def test_connection():
    print(f"🔗 正在连接 {FUNASR_URL} ...")
    try:
        async with websockets.connect(FUNASR_URL, open_timeout=10, close_timeout=5) as ws:
            print("✅ 连接成功!")
            # 发送测试消息
            await ws.send('{"mode": "2pass"}')
            print("📤 已发送测试消息")
            # 等待响应
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                print(f"📥 收到响应: {response}")
            except asyncio.TimeoutError:
                print("⏱️ 等待响应超时（这可能是正常的，服务在等待音频数据）")
    except ConnectionRefusedError:
        print("❌ 连接被拒绝 - 请检查 FunASR 服务是否运行")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ 无效状态码: {e}")
    except Exception as e:
        print(f"❌ 连接失败: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
