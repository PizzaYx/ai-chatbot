
import os
import django
import sys
import uuid

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from api.chat import get_chat_history
from chat.models import ChatSession, ChatMessage
from llama_index.core.llms import ChatMessage as LlamaChatMessage

print("--- Start Deep Debug ---")

# 1. Test Session Creation
print("1. Testing Session Creation...")
try:
    session_id = str(uuid.uuid4())
    s = ChatSession.objects.create(id=session_id, title="Debug Session")
    print(f"   Created session: {s.id}")
except Exception as e:
    print(f"   FAIL: {e}")
    sys.exit(1)

# 2. Test Message Creation
print("2. Testing Message Creation...")
try:
    ChatMessage.objects.create(session=s, role="user", content="Hello")
    ChatMessage.objects.create(session=s, role="ai", content="Hi there")
    print("   Created messages.")
except Exception as e:
    print(f"   FAIL: {e}")
    sys.exit(1)

# 3. Test History Retrieval (The suspected bug)
print("3. Testing get_chat_history...")
try:
    history = get_chat_history(session_id)
    print(f"   Retrieved {len(history)} items.")
    for i, h in enumerate(history):
        print(f"   Item {i}: role={h.role}, content={h.content}")
except Exception as e:
    print(f"   FAIL in get_chat_history: {e}")
    traceback.print_exc()

# 4. Test LLM and VectorStore
from documents.services import init_llm, get_vector_store
print("4. Testing LLM Init...")
try:
    llm = init_llm("gpt-3.5-turbo") # Or None
    print(f"   LLM initialized: {llm}")
except Exception as e:
    print(f"   FAIL LLM Init: {e}")
    import traceback
    traceback.print_exc()

print("5. Testing Vector Store Init...")
try:
    vs = get_vector_store()
    print(f"   Vector Store initialized.")
except Exception as e:
    print(f"   FAIL Vector Store: {e}")
    import traceback
    traceback.print_exc()

print("--- End Debug ---")
