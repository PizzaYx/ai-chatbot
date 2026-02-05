"""
TTS API - 语音合成接口

使用 Edge-TTS 生成高质量语音
"""

import asyncio
import re
import edge_tts
from ninja import Router
from django.http import HttpResponse
from pydantic import BaseModel

router = Router(tags=["TTS"])


def clean_text_for_tts(text: str) -> str:
    """
    清理文本，移除 Markdown 格式符号和 emoji，使 TTS 朗读更自然
    """
    # 移除所有 emoji（只保留中文、英文、数字、标点符号和空白）
    # 这个方法更彻底，不会遗漏任何 emoji
    text = re.sub(
        r'[^\u4e00-\u9fff'      # 中文
        r'\u3000-\u303f'        # 中文标点  
        r'a-zA-Z0-9'            # 英文和数字
        r'\s'                   # 空白字符
        r'，。！？、；：""''（）【】《》—…·'  # 中文标点
        r',.!?;:\'"()\[\]{}<>\-_/\\@#$%^&*+=~`|'  # 英文标点
        r']', 
        '', 
        text
    )
    
    # 移除代码块
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    
    # 移除 Markdown 标题符号
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    
    # 移除加粗/斜体符号
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)       # *italic*
    text = re.sub(r'__([^_]+)__', r'\1', text)       # __bold__
    text = re.sub(r'_([^_]+)_', r'\1', text)         # _italic_
    
    # 移除链接，保留文字
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 移除图片
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    
    # 移除 Markdown 列表符号
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # 移除表格分隔符
    text = re.sub(r'\|[-:]+\|', '', text)
    text = re.sub(r'^\||\|$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|', '，', text)  # 表格竖线替换为逗号
    
    # 移除引用符号
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # 移除水平线
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    
    # 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


class TTSRequest(BaseModel):
    """TTS 请求体"""
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"  # 默认音色


@router.post("/speak")
def speak(request, data: TTSRequest):
    """
    文本转语音

    - **text**: 要转换的文本
    - **voice**: 音色名称（默认: zh-CN-XiaoxiaoNeural）

    返回 MP3 音频流
    """
    try:
        # 清理文本中的 Markdown 符号
        clean_text = clean_text_for_tts(data.text)
        
        if not clean_text:
            return HttpResponse("无有效文本内容", status=400, content_type="text/plain")
        
        # 使用 asyncio 运行异步函数
        audio_data = asyncio.run(_generate_audio(clean_text, data.voice))

        # 返回音频流
        response = HttpResponse(audio_data, content_type="audio/mpeg")
        response["Content-Disposition"] = 'inline; filename="speech.mp3"'
        return response

    except Exception as e:
        return HttpResponse(
            f"TTS 生成失败: {str(e)}",
            status=500,
            content_type="text/plain"
        )


async def _generate_audio(text: str, voice: str) -> bytes:
    """异步生成音频"""
    communicate = edge_tts.Communicate(text, voice)
    audio_chunks = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    return b"".join(audio_chunks)


@router.get("/voices")
def list_voices(request):
    """
    获取可用音色列表

    返回中文音色列表
    """
    voices = asyncio.run(edge_tts.list_voices())
    # 过滤中文音色
    chinese_voices = [
        {
            "name": v["Name"],
            "gender": v["Gender"],
            "locale": v["Locale"]
        }
        for v in voices
        if v["Locale"].startswith("zh-")
    ]
    return {"voices": chinese_voices}
