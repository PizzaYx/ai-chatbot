from django.db import models
from django.conf import settings
import uuid

class ChatSession(models.Model):
    """
    一次完整的对话会话 (Session)
    包含多条消息
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # 允许为空，支持匿名会话；未来对接用户系统时填入具体 User
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='chat_sessions'
    )
    # 会话标题 (通常由 AI 总结第一句生成)
    title = models.CharField(max_length=200, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # 是否被删除
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """
    具体的聊天消息
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()  # 消息内容
    
    # RAG 引用源 (存储 JSON 格式: [{"file": "x.pdf", "page": 1}])
    # RAG 引用源 (存储 JSON 格式: [{"file": "x.pdf", "page": 1}])
    sources = models.JSONField(null=True, blank=True, default=list)
    
    # 生成耗时 (毫秒)
    elapsed_time = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:30]}..."
