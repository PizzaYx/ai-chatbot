"""
STT API - 语音识别接口

使用 FunASR（阿里开源）进行语音转文字
"""

import asyncio
import json
import base64
from ninja import Router
from django.http import JsonResponse
from pydantic import BaseModel
import websockets

router = Router(tags=["STT"])

# FunASR 服务地址（通过 frp 穿透）
FUNASR_WS_URL = "ws://117.72.92.10:8889"


class STTRequest(BaseModel):
    """STT 请求体"""
    audio: str  # Base64 编码的音频数据
    format: str = "pcm"  # 音频格式：pcm, wav, mp3
    sample_rate: int = 16000  # 采样率


class STTResponse(BaseModel):
    """STT 响应体"""
    success: bool
    text: str = ""
    error: str = ""


@router.post("/recognize", response=STTResponse)
def recognize(request, data: STTRequest):
    """
    语音识别

    - **audio**: Base64 编码的音频数据
    - **format**: 音频格式（pcm/wav/mp3）
    - **sample_rate**: 采样率（默认 16000）

    返回识别的文字
    """
    try:
        # 解码 Base64 音频
        audio_bytes = base64.b64decode(data.audio)
        
        # 调用 FunASR 进行识别
        result = asyncio.run(_recognize_audio(audio_bytes, data.format, data.sample_rate))
        
        return STTResponse(success=True, text=result)
    
    except Exception as e:
        return STTResponse(success=False, error=str(e))


async def _recognize_audio(audio_data: bytes, audio_format: str, sample_rate: int) -> str:
    """
    调用 FunASR WebSocket 进行语音识别
    """
    try:
        async with websockets.connect(
            FUNASR_WS_URL, 
            open_timeout=10,
            close_timeout=5
        ) as ws:
            # 发送开始消息
            start_msg = {
                "mode": "offline",  # 离线模式，一次性发送完整音频
                "chunk_size": [5, 10, 5],
                "wav_name": "audio",
                "is_speaking": True,
                "wav_format": audio_format,
                "audio_fs": sample_rate
            }
            await ws.send(json.dumps(start_msg))
            
            # 发送音频数据
            await ws.send(audio_data)
            
            # 发送结束消息
            end_msg = {
                "is_speaking": False
            }
            await ws.send(json.dumps(end_msg))
            
            # 接收识别结果
            full_text = ""
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30)
                    result = json.loads(response)
                    
                    if "text" in result:
                        full_text += result["text"]
                    
                    # 检查是否完成
                    if result.get("is_final", False) or result.get("mode") == "offline":
                        break
                        
                except asyncio.TimeoutError:
                    break
            
            return full_text.strip()
            
    except websockets.exceptions.ConnectionClosed:
        raise Exception("FunASR 连接已关闭")
    except Exception as e:
        raise Exception(f"语音识别失败: {str(e)}")


@router.get("/status")
def status(request):
    """
    检查 FunASR 服务状态
    """
    try:
        result = asyncio.run(_check_funasr_status())
        return {"status": "online" if result else "offline", "url": FUNASR_WS_URL}
    except Exception as e:
        return {"status": "error", "error": str(e), "url": FUNASR_WS_URL}


async def _check_funasr_status() -> bool:
    """检查 FunASR 是否在线"""
    try:
        async with websockets.connect(
            FUNASR_WS_URL,
            open_timeout=5,
            close_timeout=2
        ) as ws:
            return True
    except:
        return False
