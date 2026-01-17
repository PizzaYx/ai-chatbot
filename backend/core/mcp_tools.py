"""
MCP 工具加载模块
从数据库加载已启用的 MCP 服务并转换为 LlamaIndex FunctionTool
"""
from typing import List
import asyncio

# 缓存已加载的工具
_mcp_tools_cache = None
_mcp_cache_timestamp = None
_tool_server_map = {} # tool_name -> server_name

def get_tool_server_map():
    return _tool_server_map

def get_mcp_tools() -> List:
    """
    获取所有已启用且连接成功的 MCP 工具
    使用缓存避免重复加载
    """
    global _mcp_tools_cache, _mcp_cache_timestamp, _tool_server_map
    
    try:
        from system.models import MCPServerConfig
        import django
        
        if not django.apps.apps.ready:
            return []
        
        # 获取所有已启用且连接成功的 MCP 配置
        active_configs = MCPServerConfig.objects.filter(
            is_active=True,
            status='connected'
        )
        
        if not active_configs.exists():
            return []
        
        # 检查缓存是否有效（如果配置没变化就用缓存）
        latest_update = max(c.updated_at for c in active_configs)
        if _mcp_tools_cache is not None and _mcp_cache_timestamp == latest_update:
            return _mcp_tools_cache
        
        # 加载所有工具
        all_tools = []
        new_map = {}
        
        for config in active_configs:
            try:
                tools = _load_mcp_tools_sync(config)
                all_tools.extend(tools)
                
                # 建立映射
                for tool in tools:
                    t_name = tool.metadata.name if hasattr(tool, 'metadata') else tool.name
                    new_map[t_name] = config.name
                    
                print(f"✅ 加载 MCP 工具: {config.name} ({len(tools)} 个工具)")
            except Exception as e:
                print(f"⚠️ 加载 MCP 工具失败 ({config.name}): {e}")
                import traceback
                traceback.print_exc()
        
        # 更新缓存
        _mcp_tools_cache = all_tools
        _tool_server_map = new_map
        _mcp_cache_timestamp = latest_update
        
        return all_tools
        
    except Exception as e:
        print(f"⚠️ 获取 MCP 工具失败: {e}")
        return []


def _load_mcp_tools_sync(config) -> List:
    """同步加载单个 MCP 配置的工具"""
    from llama_index.tools.mcp import get_tools_from_mcp_url
    from system.models import MCPServerConfig
    
    # 根据配置类型获取 URL
    if config.server_type == MCPServerConfig.ServerType.STDIO:
        # STDIO 模式：需要启动本地进程，这需要特殊处理
        # 暂时返回缓存的 available_tools
        if config.available_tools:
            from llama_index.core.tools import FunctionTool
            tools = []
            for tool_info in config.available_tools:
                # 创建简单的工具包装
                def make_tool_fn(name, desc):
                    def tool_fn(**kwargs):
                        return f"工具 {name} 被调用，参数: {kwargs}"
                    tool_fn.__name__ = name
                    tool_fn.__doc__ = desc
                    return tool_fn
                
                fn = make_tool_fn(tool_info.get('name', 'unknown'), tool_info.get('description', ''))
                tools.append(FunctionTool.from_defaults(fn=fn, name=tool_info.get('name', 'unknown')))
            return tools
        return []
    else:
        # HTTP 模式：直接连接
        if not config.endpoint_url:
            return []
        
        # 使用异步函数的同步包装
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        from llama_index.tools.mcp import aget_tools_from_mcp_url
        tools = loop.run_until_complete(aget_tools_from_mcp_url(config.endpoint_url))
        return tools


def get_tool_descriptions() -> str:
    """获取所有工具的描述，用于提示词"""
    tools = get_mcp_tools()
    if not tools:
        return ""
    
    descriptions = []
    for tool in tools:
        name = tool.metadata.name if hasattr(tool, 'metadata') else getattr(tool, 'name', 'unknown')
        desc = tool.metadata.description if hasattr(tool, 'metadata') else ''
        descriptions.append(f"- {name}: {desc or '无描述'}")
    
    return "\n".join(descriptions)
