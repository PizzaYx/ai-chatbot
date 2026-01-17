"""
系统配置管理后台
保留所有功能，优化界面布局
"""
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import LLMConfig, MCPServerConfig, PROVIDER_PRESETS


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    """大模型配置管理"""
    
    list_display = ['name', 'provider', 'model_name', 'is_active_badge']
    list_filter = ['provider', 'is_active']
    search_fields = ['name']
    
    actions = ['refresh_models']

    def is_active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color: #10b981; font-weight: bold;">✅ 默认</span>')
        return ""
    is_active_badge.short_description = "状态"

    fieldsets = (
        (None, {
            'fields': ('name', 'provider', 'api_key', 'model_name', 'is_active'),
            'description': '选择服务商，填写 API Key 和模型名称'
        }),
        ('高级配置', {
            'fields': ('base_url', 'available_models', 'last_synced'),
            'classes': ('collapse',),
            'description': 'Base URL 通常自动填充，无需修改'
        }),
    )
    
    readonly_fields = ['available_models', 'last_synced']
    
    @admin.action(description="🔄 刷新模型列表")
    def refresh_models(self, request, queryset):
        """从 API 获取可用模型列表"""
        import requests
        
        for config in queryset:
            try:
                models = self._fetch_models(config)
                config.available_models = models
                config.last_synced = timezone.now()
                config.save()
                
                models_str = ', '.join(models[:5])
                if len(models) > 5:
                    models_str += f' ... (共 {len(models)} 个)'
                
                self.message_user(
                    request,
                    f"✅ {config.name}: {models_str}",
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ {config.name}: {e}",
                    messages.ERROR
                )
    
    def _fetch_models(self, config: LLMConfig) -> list:
        """根据 provider 调用对应的 API 获取模型列表"""
        import requests
        
        headers = {"Authorization": f"Bearer {config.api_key}"}
        
        if config.provider == 'deepseek':
            url = "https://api.deepseek.com/v1/models"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [m['id'] for m in data.get('data', [])]
        
        elif config.provider == 'openai':
            url = "https://api.openai.com/v1/models"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            all_models = [m['id'] for m in data.get('data', [])]
            chat_models = [m for m in all_models if any(k in m for k in ['gpt', 'o1', 'o3', 'chatgpt'])]
            return sorted(chat_models)
        
        else:
            # 通义千问、Claude 等使用静态预设
            return PROVIDER_PRESETS.get(config.provider, {}).get('models', [])


@admin.register(MCPServerConfig)
class MCPServerConfigAdmin(admin.ModelAdmin):
    """MCP 服务配置管理"""
    
    list_display = ['name', 'server_type', 'status_badge', 'tools_display', 'is_active']
    list_filter = ['server_type', 'status', 'is_active']
    search_fields = ['name']
    readonly_fields = ['status', 'available_tools', 'last_checked', 'error_message']
    
    def status_badge(self, obj):
        icons = {'unknown': '⚪', 'connected': '🟢', 'failed': '🔴'}
        return f"{icons.get(obj.status, '⚪')} {obj.get_status_display()}"
    status_badge.short_description = '状态'
    
    def tools_display(self, obj):
        if not obj.available_tools:
            return "-"
        tools = obj.available_tools[:3]
        names = [t.get('name', str(t)) if isinstance(t, dict) else str(t) for t in tools]
        result = ', '.join(names)
        if len(obj.available_tools) > 3:
            result += f' (+{len(obj.available_tools) - 3})'
        return result
    tools_display.short_description = '工具'

    fieldsets = (
        (None, {
            'fields': ('name', 'server_type', 'is_active'),
        }),
        ('STDIO 配置', {
            'fields': ('command', 'args', 'env_vars'),
            'classes': ('collapse',),
            'description': '本地进程模式: 填写启动命令，如 npx -y @anthropic/mcp-server-fetch'
        }),
        ('Streamable HTTP 配置', {
            'fields': ('endpoint_url',),
            'classes': ('collapse',),
            'description': '远程服务模式: 填写 HTTP 端点 URL'
        }),
        ('其他', {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
        ('检测结果', {
            'fields': ('status', 'available_tools', 'last_checked', 'error_message'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['test_connection']
    
    @admin.action(description="🔍 检测连接")
    def test_connection(self, request, queryset):
        """测试 MCP Server 连接"""
        for config in queryset:
            try:
                tools = self._test_mcp_connection(config)
                config.status = MCPServerConfig.Status.CONNECTED
                config.available_tools = tools
                config.error_message = ''
                config.last_checked = timezone.now()
                config.save()
                self.message_user(
                    request, 
                    f"✅ {config.name}: 发现 {len(tools)} 个工具",
                    messages.SUCCESS
                )
            except Exception as e:
                config.status = MCPServerConfig.Status.FAILED
                config.error_message = str(e)
                config.last_checked = timezone.now()
                config.save()
                self.message_user(
                    request, 
                    f"❌ {config.name}: {e}",
                    messages.ERROR
                )
    
    def _test_mcp_connection(self, config: MCPServerConfig) -> list:
        """测试 MCP 连接"""
        from llama_index.tools.mcp import McpToolSpec, BasicMCPClient
        
        if config.server_type == MCPServerConfig.ServerType.STDIO:
            if not config.command:
                raise ValueError("STDIO 模式需要填写启动命令")
            # 使用 command 作为 command_or_url
            client = BasicMCPClient(
                command_or_url=config.command,
                args=config.args or [],
                env=config.env_vars or {}
            )
        else:
            # Streamable HTTP 模式
            if not config.endpoint_url:
                raise ValueError("Streamable HTTP 模式需要填写 Endpoint URL")
            client = BasicMCPClient(
                command_or_url=config.endpoint_url
            )
        
        mcp_tool = McpToolSpec(client=client)
        tools = mcp_tool.to_tool_list()
        return [{'name': t.metadata.name, 'description': t.metadata.description or ''} for t in tools]
