from ninja import Router, UploadedFile, File
from ninja.errors import HttpError
from documents.models import Document
from documents.services import index_document
from django.conf import settings
import os
import shutil

router = Router(tags=["documents"])

@router.post("/upload", summary="上传文档并建立索引")
def upload_document(request, file: UploadedFile = File(...)):
    """
    上传 PDF 或其他文档，并触发后台索引流程
    """
    # 1. 验证文件类型 (简单验证)
    allowed_types = ['.pdf', '.txt', '.md']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_types:
        raise HttpError(400, f"不支持的文件类型: {ext}。仅支持: {', '.join(allowed_types)}")

    # 2. 保存文件到 Document 模型
    # Django 的 FileField 会自动处理文件保存，但我们需要手动创建实例
    doc = Document.objects.create(
        title=file.name,
        file=file  # Ninja 的 UploadedFile 兼容 Django FileField
    )
    
    # 3. 触发索引 (同步或异步)
    # 在生产环境中，这里应该使用 Celery 异步任务
    # 开发环境下为了方便验证，我们先用同步调用
    success = index_document(doc.id)
    
    if not success:
        # 重新获取最新的状态信息（包含错误消息）
        doc.refresh_from_db()
        return {
            "success": False,
            "message": "文档上传成功但索引失败",
            "document_id": doc.id,
            "error": doc.error_message
        }

    return {
        "success": True,
        "message": "文档上传并索引成功",
        "document_id": doc.id,
        "title": doc.title
    }
