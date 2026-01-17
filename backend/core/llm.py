import os
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding

# 全局缓存
_llm_instance = None
_embed_instance = None
_current_config_id = None  # 用于记录当前使用的配置ID，检测变更

def init_llm():
    """
    初始化与配置全局 LLM 设置
    优先从数据库 (System App) 获取配置，无配置则回退到环境变量
    支持热更新：如果数据库配置发生变化，会自动重新加载
    """
    global _llm_instance, _current_config_id
    
    # 1. 尝试从数据库获取活跃配置
    db_config = None
    try:
        from system.models import LLMConfig
        # 避免在 Django 初始化完成前调用导致 AppRegistryNotReady
        import django
        if django.apps.apps.ready:
            db_config = LLMConfig.objects.filter(is_active=True).first()
    except Exception as e:
        print(f"⚠️ 无法读取数据库 LLM 配置: {e}")

    # 2. 检查是否需要重新加载
    # 如果有数据库配置
    if db_config:
        # 如果缓存ID与当前ID不同，或者没有缓存实例，则重新初始化
        config_signature = f"{db_config.id}_{db_config.updated_at}"
        if _current_config_id != config_signature:
            print(f"🔄 检测到 LLM 配置变更，正在重新加载: {db_config.name}")
            _llm_instance = None # 强制重置
            _current_config_id = config_signature
            
            api_key = db_config.api_key
            api_base = db_config.base_url
            model_name = db_config.model_name
        else:
            # 配置未变，直接返回缓存
            return _llm_instance
            
    # 如果没有数据库配置 (回退模式)
    elif _llm_instance is None:
        # 只有在没有缓存实例时才从环境变量加载
        print("ℹ️ 未检测到数据库 LLM 配置，使用环境变量回退模式")
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        _current_config_id = "ENV"
    else:
        # 之前是环境变量模式且还没变
        return _llm_instance
    
    if not api_key:
        print("⚠️  WARNING: API_KEY 未设置，AI 功能将无法使用。")
        return None

    # 3. 配置 Embedding 模型 (保持单例)
    embed_model = init_embedding()

    # 4. 配置 LLM (大模型)
    if not api_base or "api.openai.com" in api_base:
        llm = OpenAI(
            model=model_name,
            api_key=api_key,
            api_base=api_base, # OpenAI 原生也支持 base_url，但通常不需要
            temperature=0.1,
            max_tokens=2048
        )
    else:
        llm = OpenAILike(
            model=model_name,
            api_key=api_key,
            api_base=api_base,
            is_chat_model=True,
            context_window=4096,
            temperature=0.1,
            max_tokens=2048
        )

    # 5. 绑定到全局 Settings
    Settings.llm = llm
    Settings.embed_model = embed_model
    
    _llm_instance = llm
    print(f"✅ LLM 模型初始化完成: {model_name}")
    return llm


def init_embedding():
    """
    初始化 Embedding 模型
    使用轻量级的 BGE-small-zh（中文专精，体积小）
    使用单例模式缓存，避免重复加载
    """
    global _embed_instance
    
    if _embed_instance is not None:
        return _embed_instance
    
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    
    # BGE-small-zh：体积小（~100MB）、中文效果好、内存占用低
    model_name = "BAAI/bge-small-zh-v1.5"
    
    # 强制离线模式，避免联网检查导致的超时
    os.environ["HF_HUB_OFFLINE"] = "1"
    
    print(f"⏳ 正在加载 Embedding 模型: {model_name}...")
    _embed_instance = HuggingFaceEmbedding(
        model_name=model_name,
        embed_batch_size=10,
    )
    print("✅ Embedding 模型加载完成 (已缓存)")
    return _embed_instance

