"""
文档管理模型
用于存储上传的知识库文件信息
"""
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.validators import FileExtensionValidator


class Document(models.Model):
    """知识库文档"""
    
    class Status(models.TextChoices):
        PENDING = 'pending', '待处理'
        PROCESSING = 'processing', '处理中'
        INDEXED = 'indexed', '已索引'
        FAILED = 'failed', '处理失败'
    
    # 基础信息
    title = models.CharField('文档标题', max_length=255)
    file = models.FileField(
        '文件', 
        upload_to='documents/',
        help_text="支持格式: PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, HTML, XML, EPUB",
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'docx', 'pptx', 'xlsx', 'csv', 'txt', 'md', 'html', 'xml', 'epub']
        )]
    )
    
    # 元数据
    file_size = models.PositiveIntegerField('文件大小(字节)', default=0)
    file_type = models.CharField('文件类型', max_length=50, blank=True)
    
    # 处理状态
    status = models.CharField(
        '处理状态',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    error_message = models.TextField('错误信息', blank=True)
    
    # 时间戳
    created_at = models.DateTimeField('上传时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '知识库文档'
        verbose_name_plural = '知识库文档'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # 自动填充文件信息
        if self.file:
            self.file_size = self.file.size
            if not self.file_type:
                self.file_type = self.file.name.split('.')[-1].lower()
        super().save(*args, **kwargs)


@receiver(post_delete, sender=Document)
def delete_document_embeddings(sender, instance, **kwargs):
    """
    删除文档时，同时删除向量数据库中对应的嵌入数据
    """
    from django.db import connection
    
    try:
        # 删除物理文件
        if instance.file:
            instance.file.delete(save=False)
        
        # 删除向量数据库中的嵌入
        # LlamaIndex 会覆盖 document_id 为 UUID，所以改用 title 匹配
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM data_document_embeddings 
                WHERE metadata_ ->> 'title' = %s
                """,
                [instance.title]
            )
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} embeddings for document: {instance.title} (id={instance.id})")
    except Exception as e:
        print(f"Error deleting embeddings for document {instance.id}: {e}")

