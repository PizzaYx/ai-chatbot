from django.db import models


# 预设配置：选择 provider 后自动填充 (2025年1月更新)
PROVIDER_PRESETS = {
    'deepseek': {
        'base_url': 'https://api.deepseek.com',
        'models': ['deepseek-chat', 'deepseek-reasoner'],  # V3 和 R1
        'default_model': 'deepseek-chat',
    },
    'qwen': {
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long', 'qwen-vl-max'],
        'default_model': 'qwen-plus',
    },
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4.5-preview', 'gpt-4-turbo', 'o1', 'o1-mini'],
        'default_model': 'gpt-4o-mini',
    },
    'claude': {
        'base_url': 'https://api.anthropic.com',
        'models': ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3-7-sonnet-20250219', 'claude-3-5-haiku-20241022'],
        'default_model': 'claude-sonnet-4-20250514',
    },
    'custom': {
        'base_url': '',
        'models': [],
        'default_model': '',
    },
}


class LLMConfig(models.Model):
    """大模型配置"""
    
    class Provider(models.TextChoices):
        DEEPSEEK = 'deepseek', 'DeepSeek (深度求索)'
        QWEN = 'qwen', '通义千问 (阿里云)'
        OPENAI = 'openai', 'OpenAI'
        CLAUDE = 'claude', 'Claude (Anthropic)'
        CUSTOM = 'custom', '自定义 (OpenAI 兼容)'

    name = models.CharField('配置名称', max_length=100, help_text="便于识别，例如: 公司DeepSeek账号")
    provider = models.CharField('服务商', max_length=20, choices=Provider.choices, default=Provider.DEEPSEEK)
    
    api_key = models.CharField('API Key', max_length=255, help_text="从服务商控制台获取的密钥")
    
    # 这些字段会根据 provider 自动填充，用户一般不需要改
    base_url = models.URLField(
        'Base URL', 
        blank=True, 
        help_text="通常无需修改，选择服务商后自动填充"
    )
    model_name = models.CharField(
        '模型', 
        max_length=100, 
        blank=True,
        help_text="选择服务商后会显示可用模型"
    )
    
    # 动态获取的模型列表
    available_models = models.JSONField(
        '可用模型列表',
        default=list,
        blank=True,
        help_text="从 API 动态获取的模型列表"
    )
    last_synced = models.DateTimeField('上次同步时间', null=True, blank=True)
    
    is_active = models.BooleanField('设为默认', default=False, help_text="系统中只能有一个默认模型")
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '大模型配置'
        verbose_name_plural = '大模型配置'
        ordering = ['-is_active', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    def save(self, *args, **kwargs):
        # 如果用户没填 base_url 或 model_name，使用预设值
        preset = PROVIDER_PRESETS.get(self.provider, {})
        if not self.base_url and preset.get('base_url'):
            self.base_url = preset['base_url']
        if not self.model_name and preset.get('default_model'):
            self.model_name = preset['default_model']
        
        # 保证只有一个配置是 active 的
        if self.is_active:
            LLMConfig.objects.filter(is_active=True).exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs)


class MCPServerConfig(models.Model):
    """MCP 服务配置 (Model Context Protocol)"""
    
    class ServerType(models.TextChoices):
        STDIO = 'stdio', 'STDIO (本地进程)'
        HTTP = 'http', 'Streamable HTTP (远程服务)'
    
    class Status(models.TextChoices):
        UNKNOWN = 'unknown', '未检测'
        CONNECTED = 'connected', '已连接'
        FAILED = 'failed', '连接失败'

    name = models.CharField('服务名称', max_length=100, help_text="例如: Weather, Brave Search")
    description = models.TextField('描述', blank=True, help_text="这个 MCP 服务的用途说明")
    
    server_type = models.CharField(
        '连接方式', 
        max_length=10, 
        choices=ServerType.choices, 
        default=ServerType.STDIO
    )
    
    # STDIO 模式配置
    command = models.CharField(
        '启动命令', 
        max_length=500, 
        blank=True,
        help_text="STDIO 模式的启动命令，例如: npx -y @anthropic/mcp-server-fetch"
    )
    args = models.JSONField(
        '命令参数', 
        default=list, 
        blank=True,
        help_text="命令行参数列表，例如: [\"--port\", \"3000\"]"
    )
    
    # SSE 模式配置
    endpoint_url = models.URLField(
        'SSE Endpoint', 
        blank=True, 
        null=True,
        help_text="SSE 模式的服务端点 URL"
    )
    
    # 通用配置
    env_vars = models.JSONField(
        '环境变量', 
        default=dict, 
        blank=True,
        help_text="传递给 MCP Server 的环境变量，例如: {\"API_KEY\": \"xxx\"}"
    )
    
    is_active = models.BooleanField('启用', default=True)
    
    # 检测状态
    status = models.CharField(
        '连接状态', 
        max_length=20, 
        choices=Status.choices, 
        default=Status.UNKNOWN
    )
    available_tools = models.JSONField(
        '可用工具', 
        default=list, 
        blank=True,
        help_text="检测成功后自动填充的工具列表"
    )
    last_checked = models.DateTimeField('上次检测时间', null=True, blank=True)
    error_message = models.TextField('错误信息', blank=True)
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = 'MCP 服务配置'
        verbose_name_plural = 'MCP 服务配置'
        ordering = ['-is_active', 'name']

    def __str__(self):
        status_icon = {'unknown': '⚪', 'connected': '🟢', 'failed': '🔴'}.get(self.status, '⚪')
        return f"{status_icon} {self.name}"
