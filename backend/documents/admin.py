"""
文档管理后台配置 - 简化版
"""
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import Document
import threading


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """知识库文档管理"""
    
    list_display = ['title', 'file_type', 'file_size_display', 'status_badge', 'created_at']
    list_filter = ['status', 'file_type']
    search_fields = ['title']
    readonly_fields = ['status', 'error_message']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'file'),
            'description': '上传文档后点击 "索引文档" 将其加入知识库'
        }),
        ('状态', {
            'fields': ('status', 'error_message'),
            'classes': ('collapse',),
        }),
    )
    
    def file_size_display(self, obj):
        """友好显示文件大小"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024*1024):.1f} MB"
    file_size_display.short_description = '大小'
    
    def status_badge(self, obj):
        """彩色状态标签"""
        colors = {
            'pending': ('#f59e0b', '#fef3c7'),
            'processing': ('#3b82f6', '#dbeafe'),
            'indexed': ('#10b981', '#d1fae5'),
            'failed': ('#ef4444', '#fee2e2'),
        }
        text_color, bg_color = colors.get(obj.status, ('#6b7280', '#f3f4f6'))
        return format_html(
            '<span style="background:{}; color:{}; padding:4px 12px; border-radius:12px; font-size:12px;">{}</span>',
            bg_color, text_color, obj.get_status_display()
        )
    status_badge.short_description = '状态'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.status = Document.Status.PENDING
        super().save_model(request, obj, form, change)
    
    @admin.action(description="🚀 索引文档")
    def index_selected_documents(self, request, queryset):
        """批量索引 - 后台执行"""
        from .services import index_document
        
        count = queryset.count()
        queryset.update(status=Document.Status.PROCESSING)
        
        def background_index(doc_ids):
            for doc_id in doc_ids:
                try:
                    index_document(doc_id)
                except Exception as e:
                    print(f"Index error {doc_id}: {e}")
        
        doc_ids = list(queryset.values_list('id', flat=True))
        thread = threading.Thread(target=background_index, args=(doc_ids,))
        thread.daemon = True
        thread.start()
        
        self.message_user(request, f"已启动 {count} 个文档的索引任务", messages.SUCCESS)

    @admin.action(description="🗑️ 删除文档")
    def delete_selected_documents(self, request, queryset):
        """删除文档及向量数据"""
        count = queryset.count()
        for doc in queryset:
            doc.delete()
        self.message_user(request, f"已删除 {count} 个文档", messages.SUCCESS)
    
    actions = ['index_selected_documents', 'delete_selected_documents']
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
