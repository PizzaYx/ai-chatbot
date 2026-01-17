"""
文档索引服务
使用 LlamaIndex 解析文档并建立向量索引
"""
import os
import logging
from pathlib import Path

from django.conf import settings

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings as LlamaSettings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.postgres import PGVectorStore

from core.llm import init_llm, init_embedding

logger = logging.getLogger(__name__)


def get_vector_store():
    """获取 Postgres 向量存储连接"""
    return PGVectorStore.from_params(
        host=os.environ.get('DB_HOST', 'db'),
        port=os.environ.get('DB_PORT', '5432'),
        database=os.environ.get('DB_NAME', 'chatbot'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'postgres'),
        table_name="document_embeddings",
        embed_dim=512,  # BGE-small-zh 的向量维度
    )


def index_document(document_id: int) -> bool:
    """
    索引单个文档
    
    Args:
        document_id: Document 模型的 ID
        
    Returns:
        bool: 是否成功
    """
    from documents.models import Document  # 避免循环导入
    from llama_index.readers.file import PDFReader
    
    try:
        doc = Document.objects.get(id=document_id)
        doc.status = Document.Status.PROCESSING
        doc.save(update_fields=['status'])
        
        # 获取文件路径
        file_path = Path(settings.MEDIA_ROOT) / str(doc.file)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        logger.info(f"开始索引文档: {doc.title} ({file_path})")
        
        # 1. 初始化 LLM 和 Embedding
        llm = init_llm()
        embed_model = init_embedding()
        
        # 配置全局设置
        LlamaSettings.llm = llm
        LlamaSettings.embed_model = embed_model
        LlamaSettings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
        
        # 2. 读取文档（根据文件类型选择解析器）
        file_ext = file_path.suffix.lower()
        
        if file_ext == '.pdf':
            # 使用 pdfplumber 解析 PDF（对中文更友好）
            import pdfplumber
            from llama_index.core import Document as LlamaDocument
            
            documents = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        documents.append(LlamaDocument(
                            text=text,
                            metadata={"page": i + 1, "source": str(file_path)}
                        ))
            
            if not documents:
                raise ValueError("PDF 解析失败：无法提取任何文本内容")
        else:
            # 其他格式使用通用读取器
            reader = SimpleDirectoryReader(input_files=[str(file_path)])
            documents = reader.load_data()
        
        # 添加元数据
        for llamadoc in documents:
            llamadoc.metadata['document_id'] = document_id
            llamadoc.metadata['title'] = doc.title
            llamadoc.metadata['file_name'] = doc.file.name if doc.file else doc.title
        
        logger.info(f"文档解析完成，共 {len(documents)} 页")
        
        # 3. 创建向量存储和索引
        vector_store = get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True,
        )
        
        # 4. 更新状态
        doc.status = Document.Status.INDEXED
        doc.error_message = ''
        doc.save(update_fields=['status', 'error_message'])
        
        logger.info(f"文档索引成功: {doc.title}")
        return True
        
    except Exception as e:
        logger.error(f"文档索引失败: {e}", exc_info=True)
        try:
            doc = Document.objects.get(id=document_id)
            doc.status = Document.Status.FAILED
            doc.error_message = str(e)
            doc.save(update_fields=['status', 'error_message'])
        except:
            pass
        return False


def query_documents(question: str, top_k: int = 3) -> str:
    """
    查询知识库
    
    Args:
        question: 用户问题
        top_k: 返回最相关的文档数量
        
    Returns:
        str: 检索到的相关内容
    """
    try:
        # 初始化
        llm = init_llm()
        embed_model = init_embedding()
        LlamaSettings.llm = llm
        LlamaSettings.embed_model = embed_model
        
        # 连接向量存储
        vector_store = get_vector_store()
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        # 创建查询引擎
        query_engine = index.as_query_engine(similarity_top_k=top_k)
        
        # 执行查询
        response = query_engine.query(question)
        
        return str(response)
        
    except Exception as e:
        logger.error(f"知识库查询失败: {e}", exc_info=True)
        return ""
