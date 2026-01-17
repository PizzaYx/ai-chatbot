from ninja import Router, Schema
from django.http import StreamingHttpResponse
from django.contrib.auth.models import User
from typing import List, Optional
import json
import uuid
import time
from datetime import datetime
# LlamaIndex
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.llms import ChatMessage as LlamaChatMessage
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import EmbeddingSingleSelector

# Local Imports
from chat.models import ChatSession, ChatMessage
from documents.services import get_vector_store, init_llm, init_embedding
from core.mcp_tools import get_mcp_tools, get_tool_server_map
from api.auth import decode_token  # 导入 JWT 解码函数

router = Router(tags=["Chat"])


def get_current_user_from_request(request) -> Optional[User]:
    """
    从请求的 Authorization header 中提取并验证用户
    这是一个可选的认证 - 如果没有 Token 或 Token 无效，返回 None
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]  # 去掉 "Bearer " 前缀
    payload = decode_token(token)
    if payload is None:
        return None
    
    user_id = payload.get("user_id")
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None

# --- Schemas ---
class MessageSchema(Schema):
    role: str  # 'user' | 'ai'
    text: str
    sources: Optional[List[dict]] = None
    elapsed: Optional[int] = None # 耗时 (ms)

class ChatRequest(Schema):
    messages: List[MessageSchema] 
    session_id: Optional[str] = None # 前端传来的会话ID
    model: Optional[str] = None
    use_rag: Optional[bool] = True

class ChatResponse(Schema):
    session_id: str
    message: MessageSchema

class SessionSchema(Schema):
    id: str
    title: str
    updated_at: str
    message_count: int

# --- Core Logic ---

def get_chat_history(session_id: str) -> List[LlamaChatMessage]:
    """从数据库加载历史记录"""
    if not session_id:
        return []
    
    # 获取最近 20 条消息 (先按时间倒序取最新的，再转回正序)
    db_messages = ChatMessage.objects.filter(
        session_id=session_id
    ).order_by('-created_at')[:20]
    
    # 转回正序
    db_messages = reversed(db_messages)
    
    history = []
    for msg in db_messages:
        # 映射数据库角色到 LlamaIndex 角色 (ai -> assistant)
        role = "assistant" if msg.role == "ai" else msg.role
        history.append(LlamaChatMessage(role=role, content=msg.content))
    return history

def stream_generator(current_message: str, history: List[LlamaChatMessage], model_name: str, use_rag: bool, session_id: str):
    """
    流式生成器函数: MCP 工具 / 混合检索 -> 决定 Tool/RAG/Chat -> Stream
    """
    start_time = time.time() # 开始计时
    llm = init_llm()
    embed_model = init_embedding()
    Settings.llm = llm
    Settings.embed_model = embed_model
    
    # --- 0. 加载 MCP 工具 ---
    mcp_tools = get_mcp_tools()
    if mcp_tools:
        print(f"🔧 已加载 {len(mcp_tools)} 个 MCP 工具")
    
    # --- 1. 向量检索 ---
    retrieved_nodes = []
    max_score = 0.0
    
    if use_rag:
        try:
            vector_store = get_vector_store()
            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            retriever = index.as_retriever(similarity_top_k=3)
            retrieved_nodes = retriever.retrieve(current_message)
            
            if retrieved_nodes:
                max_score = max(node.score for node in retrieved_nodes if node.score is not None)
                print(f"Vector Retrieval: max_score={max_score:.3f}, nodes={len(retrieved_nodes)}")
        except Exception as e:
            print(f"Retrieval Error: {e}")
    
    # --- 2. 混合判断：向量分数 OR 关键词匹配 ---
    VECTOR_THRESHOLD = 0.5  # 向量相似度阈值 (高，用于语义匹配)
    
    # 检查关键词是否在数据库中直接命中 (精确匹配)
    keyword_match = False
    keyword_results = []
    is_exact_match = False  # 标记是否精确匹配
    
    if current_message.strip() and len(current_message.strip()) > 2:
        try:
            from django.db import connection
            import re
            query_text = current_message.strip()
            
            # 方法1：精确匹配整个查询
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT text, metadata_ FROM data_document_embeddings WHERE text ILIKE %s LIMIT 3",
                    [f"%{query_text}%"]
                )
                rows = cursor.fetchall()
                
                if rows:
                    is_exact_match = True
                    print(f"Keyword Match (exact): found {len(rows)} documents")
                else:
                    # 方法2：如果精确匹配失败，尝试拆分关键词匹配
                    chinese_chars = re.findall(r'[\u4e00-\u9fa5]', query_text)
                    chinese_str = ''.join(chinese_chars)
                    
                    if len(chinese_str) >= 4:
                        keywords = []
                        for i in range(0, len(chinese_str) - 1, 2):
                            keywords.append(chinese_str[i:i+2])
                        keywords = list(set(keywords))[:3]
                        
                        if len(keywords) >= 2:
                            conditions = " AND ".join([f"text ILIKE %s" for _ in keywords])
                            params = [f"%{kw}%" for kw in keywords]
                            cursor.execute(
                                f"SELECT text, metadata_ FROM data_document_embeddings WHERE {conditions} LIMIT 3",
                                params
                            )
                            rows = cursor.fetchall()
                            if rows:
                                is_exact_match = False  # 模糊匹配
                                print(f"Keyword Match (fuzzy): found {len(rows)} docs with keywords {keywords}")
                
                if rows:
                    keyword_match = True
                    keyword_results = rows
        except Exception as e:
            print(f"Keyword search error: {e}")
    
    # --- 2. 决策逻辑 ---
    # 优先级：RAG > 工具 > 普通对话
    # 使用向量语义匹配来判断是否需要工具
    
    # 计算用户问题和工具描述的相似度
    tool_match_score = 0.0
    matched_tool_name = None
    
    if mcp_tools and embed_model:
        try:
            # 把用户问题做成 embedding
            query_embedding = embed_model.get_text_embedding(current_message)
            
            # 计算和每个工具描述的相似度
            for tool in mcp_tools:
                tool_desc = f"{tool.metadata.name}: {tool.metadata.description or ''}"
                tool_embedding = embed_model.get_text_embedding(tool_desc)
                
                # 计算余弦相似度
                import numpy as np
                similarity = np.dot(query_embedding, tool_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(tool_embedding)
                )
                
                if similarity > tool_match_score:
                    tool_match_score = similarity
                    matched_tool_name = tool.metadata.name
            
            print(f"Tool Match: max_score={tool_match_score:.3f}, tool={matched_tool_name}")
        except Exception as e:
            print(f"Tool matching error: {e}")
    
    # 决策阈值
    TOOL_THRESHOLD = 0.4  # 工具匹配阈值，降低以更容易触发
    RAG_THRESHOLD = 0.5   # RAG 阈值
    
    # 决策逻辑：比较分数，选更高的
    # 如果都低于阈值 → 普通对话
    rag_score = max_score if max_score >= RAG_THRESHOLD or (keyword_match and max_score >= 0.3) else 0
    tool_score = tool_match_score if tool_match_score >= TOOL_THRESHOLD else 0
    
    if rag_score > 0 and rag_score >= tool_score:
        selected_mode = "rag"
    elif tool_score > 0 and tool_score > rag_score:
        selected_mode = "tool"
    else:
        selected_mode = "chat"
    
    print(f"Router Decision: {selected_mode} (rag={rag_score:.3f}, tool={tool_score:.3f})")
    
    full_response_text = ""
    sources = []

    try:
        # 1. RAG 分支（知识库问答）
        if selected_mode == "rag":
            print(f"  → RAG: 使用知识库回答 (exact={is_exact_match})")
            
            if keyword_match and keyword_results:
                rag_texts = [row[0] for row in keyword_results]
                rag_context = "\n\n参考资料:\n" + "\n---\n".join(rag_texts)
                import json as json_lib
                for row in keyword_results:
                    try:
                        raw_meta = row[1]
                        meta = json_lib.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta if isinstance(raw_meta, dict) else {})
                        file_name = meta.get("file_name") or meta.get("title") or "未知文件"
                        if "/" in str(file_name): file_name = str(file_name).split("/")[-1]
                        source_info = {"file_name": file_name, "page": meta.get("page_label")}
                        if source_info not in sources: sources.append(source_info)
                    except: pass
            else:
                rag_texts = [n.get_content() for n in retrieved_nodes]
                rag_context = "\n\n参考资料:\n" + "\n---\n".join(rag_texts)
                for node in retrieved_nodes:
                    meta = node.node.metadata if hasattr(node.node, 'metadata') else {}
                    file_name = meta.get("file_name") or "未知文件"
                    if "/" in str(file_name): file_name = str(file_name).split("/")[-1]
                    source_info = {"file_name": file_name, "page": meta.get("page_label")}
                    if source_info not in sources: sources.append(source_info)
            
            import datetime
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 获取唯一的文档来源
            unique_files = list(set([s.get("file_name", "未知") for s in sources]))
            
            # 根据匹配类型和来源数量构造不同的 System Prompt
            if is_exact_match:
                # 精确匹配，直接回答
                system_prompt = f"你是一个专业的 AI 助手。当前时间是: {current_time_str}。请根据参考资料回答问题，使用 Markdown 格式。"
            elif len(unique_files) > 1:
                # 模糊匹配 + 多个文档来源，让用户选择
                files_list = "\n".join([f"- {f}" for f in unique_files])
                system_prompt = f"""你是一个专业的 AI 助手。当前时间是: {current_time_str}。
注意：用户的查询是模糊匹配的结果，我在以下多个文档中找到了相关信息：
{files_list}

请先询问用户想要查询哪个文档的信息，不要直接给出答案。用简洁的方式列出这些文档让用户选择。"""
            else:
                # 模糊匹配 + 单一文档，询问确认
                doc_name = unique_files[0] if unique_files else "知识库"
                system_prompt = f"""你是一个专业的 AI 助手。当前时间是: {current_time_str}。
注意：用户的查询是模糊匹配的结果，我在《{doc_name}》中找到了可能相关的信息。
请先简要说明找到了什么内容，并询问用户是否是他们想要的信息。如果用户确认，再详细回答。"""
            
            messages = [LlamaChatMessage(role="system", content=system_prompt)]
            messages.extend(history)
            messages.append(LlamaChatMessage(role="user", content=f"{current_message}\n{rag_context}"))
            
            response_stream = llm.stream_chat(messages)
            for chunk in response_stream:
                if chunk.delta:
                    full_response_text += chunk.delta
                    yield json.dumps({"text": chunk.delta}, ensure_ascii=False) + "\n"
        
        # 2. 工具分支
        elif selected_mode == "tool":
            print(f"  → Tool: 调用工具 {matched_tool_name}")
            
            try:
                # 构造包含系统提示的历史
                system_msg = LlamaChatMessage(
                    role="system",
                    content="你是一个能够调用工具的智能助手。当用户询问天气、地图、位置等信息时，调用提供的工具获取实时数据。如果用户没有提供必要的参数（如城市名），请先询问用户。"
                )
                tool_history = [system_msg] + list(history)
                
                # 使用 LLM function calling
                response = llm.chat_with_tools(
                    tools=mcp_tools,
                    user_msg=current_message,
                    chat_history=tool_history,
                )
                
                # 尝试获取 tool calls，如果没有则为空列表
                try:
                    tool_calls = llm.get_tool_calls_from_response(response)
                except:
                    tool_calls = []
                
                if tool_calls:
                    # 执行工具调用
                    tool_results = []
                    for tc in tool_calls:
                        print(f"🔧 调用工具: {tc.tool_name}({tc.tool_kwargs})")

                        # 记录来源
                        tool_map = get_tool_server_map()
                        server_name = tool_map.get(tc.tool_name, tc.tool_name)
                        
                        sources.append({
                            "type": "tool",
                            "name": server_name, # 显示服务名 (如 高德地图)
                            "tool_id": tc.tool_name, # 原始工具ID
                            "args": str(tc.tool_kwargs)
                        })
                        
                        # 找到并执行工具
                        for tool in mcp_tools:
                            if tool.metadata.name == tc.tool_name:
                                try:
                                    result = tool.call(**tc.tool_kwargs)
                                    tool_results.append(f"{tc.tool_name}: {result}")
                                except Exception as te:
                                    tool_results.append(f"{tc.tool_name} 失败: {te}")
                                break
                    
                    # 用工具结果生成回答
                    tool_context = "\n".join(tool_results)
                    import datetime
                    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    messages = [
                        LlamaChatMessage(role="system", content=f"你是助手。当前时间是: {current_time_str}。根据工具返回的信息回答用户。"),
                        LlamaChatMessage(role="user", content=current_message),
                        LlamaChatMessage(role="assistant", content=f"工具返回:\n{tool_context}"),
                        LlamaChatMessage(role="user", content="请用这些信息回答我。")
                    ]
                    response_stream = llm.stream_chat(messages)
                    for chunk in response_stream:
                        if chunk.delta:
                            full_response_text += chunk.delta
                            yield json.dumps({"text": chunk.delta}, ensure_ascii=False) + "\n"
                else:
                    # LLM 判断不需要工具
                    full_response_text = str(response.message.content)
                    for i in range(0, len(full_response_text), 50):
                        yield json.dumps({"text": full_response_text[i:i+50]}, ensure_ascii=False) + "\n"
                        
            except Exception as e:
                print(f"Tool error: {e}")
                # 降级到普通对话
                messages = [LlamaChatMessage(role="system", content="你是助手。")]
                messages.extend(history)
                messages.append(LlamaChatMessage(role="user", content=current_message))
                response_stream = llm.stream_chat(messages)
                for chunk in response_stream:
                    if chunk.delta:
                        full_response_text += chunk.delta
                        yield json.dumps({"text": chunk.delta}, ensure_ascii=False) + "\n"
        
        # 3. 普通对话（最快）
        else:
            print("Router Decision: chat")
            import datetime
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_prompt = f"你是一个友好的 AI 助手。当前时间是: {current_time_str}。"
            messages = [LlamaChatMessage(role="system", content=system_prompt)]
            messages.extend(history)
            messages.append(LlamaChatMessage(role="user", content=current_message))
            
            response_stream = llm.stream_chat(messages)
            for chunk in response_stream:
                if chunk.delta:
                    full_response_text += chunk.delta
                    yield json.dumps({"text": chunk.delta}, ensure_ascii=False) + "\n"

        # 发送 Sources 和保存
        if sources:
            yield json.dumps({"sources": sources}, ensure_ascii=False) + "\n"
        
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id)
                elapsed_time = int((time.time() - start_time) * 1000) # 计算耗时 (ms)
                ChatMessage.objects.create(
                    session=session, 
                    role='ai', 
                    content=full_response_text, 
                    sources=sources,
                    elapsed_time=elapsed_time
                )
                if session.title == "New Chat":
                    session.title = current_message.strip()[:20] + ("..." if len(current_message) > 20 else "")
                    session.save(update_fields=['title'])
            except: pass

    except Exception as e:
        yield json.dumps({"text": f"Error: {str(e)}"}, ensure_ascii=False) + "\n"



@router.post("/stream", summary="流式对话 (带记忆)")
def chat_stream(request, payload: ChatRequest):
    # 1. 获取或创建 Session
    from django.core.exceptions import ValidationError
    
    session_id = payload.session_id
    session = None
    
    # 获取当前用户（如果已认证）
    current_user = get_current_user_from_request(request)
    
    if session_id:
        try:
            # 尝试获取现有 Session
            session = ChatSession.objects.get(id=session_id)
            # 如果会话没有用户但当前用户已登录，关联用户
            if not session.user and current_user:
                session.user = current_user
                session.save(update_fields=['user'])
        except (ChatSession.DoesNotExist, ValidationError):
            # 如果不存在 或 格式不对，我们就尝试新建
            try:
                # 尝试用传来的 session_id 创建可能会再次失败（如果格式不对）
                uuid.UUID(session_id) # 验证一下格式
                session = ChatSession.objects.create(id=session_id, user=current_user)
            except (ValueError, ValidationError):
                # 彻底放弃原来的 ID，生成新的
                session = ChatSession.objects.create(user=current_user)
                session_id = str(session.id)
    else:
        # 如果前端没传 ID，我们新建一个
        session = ChatSession.objects.create(user=current_user)
        session_id = str(session.id)

    # 2. 获取用户最新的一条消息
    # 之前的 payload.messages 是个列表，但现在有了历史记录，前端其实只需要发最新的一句 user message 即可。
    # 为了兼容旧逻辑，我们取 messages 列表里最后一条 user 消息。
    user_text = ""
    if payload.messages:
        user_text = payload.messages[-1].text
    
    if not user_text:
        return {"error": "No user message found"}

    # 3. 保存用户消息到数据库
    ChatMessage.objects.create(
        session=session,
        role='user',
        content=user_text
    )

    # 4. 加载历史记录 (不包含刚刚存的这条，因为要作为 prompt 单独传)
    # LlamaIndex stream_chat(message, history) 里的 history 指的是 "Previous conversation"
    history = get_chat_history(session_id)
    # 去掉刚刚存的那条 user message，防止重复 (因为 get_chat_history 会取所有)
    if history and history[-1].role == "user" and history[-1].content == user_text:
        history.pop()

    # 5. 返回流式响应
    # 我们需要在 header 里把 session_id 返给前端吗？
    # Stream Response 很难带 Header。
    # 建议前端：如果是第一次请求（没 session_id），前端收到第一帧数据时应该知道 session_id（或者我们第一帧发个元数据？）
    # 简单策略：前端自己生成 UUID session_id 传过来（UUIDv4），这样后端就不用回传了。
    
    return StreamingHttpResponse(
        stream_generator(user_text, history, payload.model, payload.use_rag, session_id),
        content_type='text/plain; charset=utf-8'
    )

@router.get("/history", response=List[MessageSchema])
def get_history(request, session_id: str):
    """获取会话历史"""
    from django.core.exceptions import ValidationError
    try:
        # 验证会话存在且属于当前用户
        current_user = get_current_user_from_request(request)
        session = ChatSession.objects.filter(id=session_id).first()
        
        # 如果会话存在且有用户归属，验证是否为当前用户
        if session and session.user and current_user and session.user != current_user:
            return []  # 无权访问其他用户的会话
        
        messages = ChatMessage.objects.filter(session_id=session_id).order_by('created_at')
        return [
            {
                "role": msg.role, 
                "text": msg.content if msg.content else "",
                "sources": msg.sources,
                "elapsed": msg.elapsed_time
            }
            for msg in messages
        ]
    except ValidationError:
        return [] # ID 格式不对就返回空
    except Exception as e:
        print(f"Error getting history: {e}")
        return []

@router.delete("/session/{session_id}", summary="删除会话")
def delete_session(request, session_id: str):
    """删除指定会话及其所有消息（仅限当前用户）"""
    from django.core.exceptions import ValidationError
    try:
        current_user = get_current_user_from_request(request)
        
        # 验证会话属于当前用户
        session = ChatSession.objects.filter(id=session_id).first()
        if session and session.user and current_user and session.user != current_user:
            return {"success": False, "error": "Permission denied"}
        
        # 删除所有消息
        deleted_count, _ = ChatMessage.objects.filter(session_id=session_id).delete()
        # 删除会话
        ChatSession.objects.filter(id=session_id).delete()
        return {"success": True, "deleted_messages": deleted_count}
    except ValidationError:
        return {"success": False, "error": "Invalid session ID"}
    except Exception as e:
        print(f"Error deleting session: {e}")
        return {"success": False, "error": str(e)}

@router.get("/sessions", response=List[SessionSchema], summary="获取会话列表")
def get_sessions(request):
    """获取当前用户的会话列表"""
    from django.db.models import Count, Q
    
    # 获取当前用户
    current_user = get_current_user_from_request(request)
    
    # 只返回当前用户的会话（如果已登录）或匿名会话
    if current_user:
        sessions = ChatSession.objects.filter(
            is_active=True,
            user=current_user
        ).annotate(
            message_count=Count('messages')
        ).order_by('-updated_at')[:20]
    else:
        # 未登录用户看不到任何会话
        return []
    
    return [
        {
            "id": str(session.id),
            "title": session.title,
            "updated_at": session.updated_at.isoformat(),
            "message_count": session.message_count
        }
        for session in sessions
    ]

@router.patch("/session/{session_id}/title", summary="更新会话标题")
def update_session_title(request, session_id: str, title: str):
    """更新会话标题"""
    from django.core.exceptions import ValidationError
    try:
        session = ChatSession.objects.get(id=session_id)
        session.title = title
        session.save(update_fields=['title'])
        return {"success": True}
    except ChatSession.DoesNotExist:
        return {"success": False, "error": "Session not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

