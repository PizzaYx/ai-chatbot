from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from ninja import NinjaAPI
from api import chat_router, documents_router, auth_router, tts_router, stt_router

# 实例化 Django Ninja API
api = NinjaAPI(
    title="AI Chatbot API",
    version="1.0.0",
    description="Enterprise AI Chatbot Backend",
    urls_namespace="api", # 避免 URL 命名冲突
)

# 注册路由模块
api.add_router("/chat", chat_router)
api.add_router("/documents", documents_router)
api.add_router("/auth", auth_router)
api.add_router("/tts", tts_router)
api.add_router("/stt", stt_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", api.urls),
]

# 开发模式下提供媒体文件和静态文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
