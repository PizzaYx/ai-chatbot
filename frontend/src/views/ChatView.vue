<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import ChatMessage from '@/components/ChatMessage.vue';
import {
    Plus, ChatDotRound, Delete, SwitchButton,
    Menu, ArrowDown, ArrowUp, Promotion, VideoPause
} from '@element-plus/icons-vue';

const router = useRouter();
const authStore = useAuthStore();

interface Message {
    role: 'user' | 'ai';
    text: string;
    sources?: any[];
    timestamp?: string;
    elapsed?: number;
}

// 初始欢迎语
const defaultMessage: Message = {
    role: 'ai',
    text: '您好！我是您的智能助手。\n\n有什么我可以帮您的吗？'
};

const isMobileMenuOpen = ref(false);
const sessionId = ref('');
const messages = ref<Message[]>([defaultMessage]);
const userInput = ref('');
const isLoading = ref(false);
const chatContainer = ref<HTMLElement | null>(null);
const abortController = ref<AbortController | null>(null);

// 历史消息折叠
const showAllMessages = ref(false);
const RECENT_MESSAGE_COUNT = 6;

const displayedMessages = computed(() => {
    if (showAllMessages.value || messages.value.length <= RECENT_MESSAGE_COUNT) {
        return messages.value;
    }
    return messages.value.slice(-RECENT_MESSAGE_COUNT);
});

const hiddenMessageCount = computed(() => {
    if (showAllMessages.value) return 0;
    return Math.max(0, messages.value.length - RECENT_MESSAGE_COUNT);
});

// 会话列表
interface Session {
    id: string; // UUID
    title: string;
    updated_at: string;
}
const sessions = ref<Session[]>([]);

onMounted(async () => {
    await loadSessions();
    const storedId = localStorage.getItem('chat_session_id');
    if (storedId) {
        sessionId.value = storedId;
        await loadHistory();
    } else {
        createNewSession();
    }
});

const loadSessions = async () => {
    try {
        const res = await fetch('/api/chat/sessions');
        if (res.ok) {
            sessions.value = await res.json();
        }
    } catch (e) {
        console.error(e);
    }
};

const switchSession = async (session: Session) => {
    sessionId.value = session.id;
    localStorage.setItem('chat_session_id', session.id);
    messages.value = [defaultMessage];
    showAllMessages.value = false;
    await loadHistory();
    isMobileMenuOpen.value = false;
};

// UUID Generator
function createUUID() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

const createNewSession = () => {
    const newId = createUUID();
    sessionId.value = newId;
    localStorage.setItem('chat_session_id', newId);
    messages.value = [defaultMessage];
    showAllMessages.value = false;
    isMobileMenuOpen.value = false;
    loadSessions();
};

const deleteSession = async (id: string) => {
    if (!confirm('确定要删除这个会话吗？')) return;
    try {
        // 注意：后端路径是 /session/ 不是 /sessions/
        const res = await fetch(`/api/chat/session/${id}`, { method: 'DELETE' });
        if (res.ok) {
            await loadSessions();
            if (sessionId.value === id) createNewSession();
        }
    } catch (e) {
        console.error(e);
    }
};

const handleLogout = () => {
    localStorage.removeItem('token');
    authStore.token = null;
    authStore.user = null;
    router.push('/login');
};

const loadHistory = async () => {
    try {
        const res = await fetch(`/api/chat/history?session_id=${sessionId.value}`);
        if (res.ok) {
            const history = await res.json();
            if (history && history.length > 0) {
                messages.value = history.map((h: any) => ({
                    role: h.role,
                    text: h.text || '', // Backend returns 'text' not 'content'
                    sources: h.sources
                }));
            } else {
                messages.value = [defaultMessage];
            }
            await nextTick();
            scrollToBottom();
        }
    } catch (e) {
        console.error(e);
    }
};

const scrollToBottom = async () => {
    await nextTick();
    if (chatContainer.value) {
        chatContainer.value.scrollTo({
            top: chatContainer.value.scrollHeight,
            behavior: 'smooth'
        });
    }
};

const stopGeneration = () => {
    if (abortController.value) {
        abortController.value.abort();
        abortController.value = null;
        isLoading.value = false;
    }
};

const sendMessage = async () => {
    if (!userInput.value.trim() || isLoading.value) return;

    const text = userInput.value;
    userInput.value = '';

    messages.value.push({
        role: 'user',
        text,
        timestamp: new Date().toISOString()
    });

    isLoading.value = true;
    abortController.value = new AbortController();

    await nextTick();
    scrollToBottom();

    const aiMsgIndex = messages.value.length;
    messages.value.push({ role: 'ai', text: '', elapsed: 0 });
    const startTime = Date.now();

    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: [{ role: 'user', text: text }], // Keep strict format
                session_id: sessionId.value
            }),
            signal: abortController.value.signal
        });

        if (!response.ok) throw new Error('Network error');
        if (!response.body) throw new Error('No stream');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    // 后端发送 {text: "..."} 或 {sources: [...]}
                    if (data.text) {
                        messages.value[aiMsgIndex].text += data.text;
                    } else if (data.sources) {
                        messages.value[aiMsgIndex].sources = data.sources;
                    } else if (data.type === 'content') {
                        // 兼容旧格式
                        messages.value[aiMsgIndex].text += data.content;
                    } else if (data.type === 'title') {
                        loadSessions();
                    } else if (data.type === 'error') {
                        messages.value[aiMsgIndex].text += `\n[Error: ${data.message}]`;
                    }
                } catch (e) { }
            }
            scrollToBottom();
        }

    } catch (e: any) {
        if (e.name === 'AbortError') messages.value[aiMsgIndex].text += '\n[已停止]';
        else messages.value[aiMsgIndex].text += '\n[网络错误]';
    } finally {
        isLoading.value = false;
        abortController.value = null;
        messages.value[aiMsgIndex].elapsed = Date.now() - startTime;
        messages.value[aiMsgIndex].timestamp = new Date().toISOString();
        await loadSessions();
    }
};

const formatTime = (timeStr: string) => {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
};
</script>

<template>
    <div class="chat-layout">
        <div v-if="isMobileMenuOpen" class="sidebar-overlay" @click="isMobileMenuOpen = false"></div>

        <aside class="sidebar" :class="{ 'sidebar--open': isMobileMenuOpen }">
            <div class="sidebar__header">
                <span style="font-size: 18px;">AI 助手</span>
                <button class="sidebar__close" @click="isMobileMenuOpen = false">×</button>
            </div>

            <div class="sidebar__actions">
                <button class="new-chat-btn" @click="createNewSession">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                    新对话
                </button>
            </div>

            <div class="sidebar__history">
                <div class="history-title">历史记录</div>
                <div v-if="sessions.length === 0" class="history-empty">暂无会话</div>
                <div v-for="session in sessions" :key="session.id" class="history-item"
                    :class="{ active: session.id === sessionId }" @click="switchSession(session)">
                    <svg class="session-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                        stroke-linejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <div class="session-info">
                        <div class="session-title">{{ session.title }}</div>
                        <div class="session-time">{{ formatTime(session.updated_at) }}</div>
                    </div>
                    <button class="delete-session-btn" @click.stop="deleteSession(session.id)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2">
                            </path>
                        </svg>
                    </button>
                </div>
            </div>

            <div class="sidebar__footer">
                <div class="user-info">
                    <div class="user-avatar">{{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
                    <span class="user-name">{{ authStore.user?.username || 'User' }}</span>
                </div>
                <button class="logout-btn" @click="handleLogout">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                </button>
            </div>
        </aside>

        <main class="main">
            <header class="mobile-header">
                <button class="menu-btn" @click="isMobileMenuOpen = true">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="3" y1="12" x2="21" y2="12"></line>
                        <line x1="3" y1="6" x2="21" y2="6"></line>
                        <line x1="3" y1="18" x2="21" y2="18"></line>
                    </svg>
                </button>
                <span class="header-title">AI 助手</span>
                <button class="new-btn" @click="createNewSession">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                </button>
            </header>

            <div ref="chatContainer" class="chat-container">
                <div class="chat-messages">
                    <div v-if="hiddenMessageCount > 0" class="history-toggle" @click="showAllMessages = true">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                        展开 {{ hiddenMessageCount }} 条历史
                    </div>
                    <div v-if="showAllMessages && messages.length > RECENT_MESSAGE_COUNT" class="history-toggle"
                        @click="showAllMessages = false">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="18 15 12 9 6 15"></polyline>
                        </svg>
                        收起历史
                    </div>

                    <ChatMessage v-for="(msg, index) in displayedMessages" :key="index" :role="msg.role"
                        :text="msg.text" :sources="msg.sources" :timestamp="msg.timestamp" :elapsed="msg.elapsed"
                        :loading="isLoading && index === displayedMessages.length - 1 && msg.role === 'ai' && !msg.text" />
                </div>
            </div>

            <div class="input-area">
                <div class="input-wrapper">
                    <textarea v-model="userInput" rows="1" placeholder="发送消息..." @keydown.enter.prevent="sendMessage"
                        :disabled="isLoading"></textarea>

                    <button v-if="isLoading" class="send-btn stop-btn" @click="stopGeneration">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                            fill="currentColor">
                            <rect x="6" y="6" width="12" height="12" rx="2" />
                        </svg>
                    </button>
                    <button v-else class="send-btn" @click="sendMessage" :disabled="!userInput.trim()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
        </main>
    </div>
</template>

<style scoped lang="scss">
.chat-layout {
    display: flex;
    height: 100vh;
    width: 100vw;
    background: #ffffff;
    color: #1f2937;
    overflow: hidden;
}

// Sidebar
.sidebar {
    width: 280px;
    height: 100%;
    background: #f9fafb;
    border-right: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;

    @media (max-width: 768px) {
        position: fixed;
        left: 0;
        top: 0;
        bottom: 0;
        z-index: 50;
        transform: translateX(-100%);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: none;

        &--open {
            transform: translateX(0);
            box-shadow: 8px 0 32px rgba(0, 0, 0, 0.15);
        }
    }
}

.sidebar-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(4px);
    z-index: 40;
}

.sidebar__header {
    padding: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 18px;
    font-weight: 700;
    color: #111827;
}

.sidebar__close {
    display: none;
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #6b7280;

    @media (max-width: 768px) {
        display: block;
    }
}

.sidebar__actions {
    padding: 0 16px 16px;
}

.new-chat-btn {
    width: 100%;
    padding: 12px 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);

    &:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
}

.sidebar__history {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px;

    &::-webkit-scrollbar {
        width: 4px;
    }

    &::-webkit-scrollbar-thumb {
        background: #d1d5db;
        border-radius: 4px;
    }
}

.history-title {
    padding: 12px 8px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.history-empty {
    padding: 20px;
    text-align: center;
    color: #9ca3af;
    font-size: 13px;
}

.history-item {
    padding: 12px;
    margin-bottom: 4px;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.15s;

    &:hover {
        background: #e5e7eb;
    }

    &.active {
        background: #dbeafe;
        color: #1e40af;

        .session-icon {
            color: #2563eb;
        }
    }
}

.session-icon {
    color: #9ca3af;
    flex-shrink: 0;
}

.session-info {
    flex: 1;
    overflow: hidden;
    min-width: 0;
}

.session-title {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 14px;
    font-weight: 500;
    color: inherit;
}

.session-time {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 2px;
}

.delete-session-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #9ca3af;
    padding: 6px;
    border-radius: 6px;
    transition: all 0.15s;
    opacity: 0;
    display: flex;
    align-items: center;
    justify-content: center;

    .history-item:hover & {
        opacity: 1;
    }

    &:hover {
        color: #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }

    // Always visible on mobile (no hover state)
    @media (max-width: 768px) {
        opacity: 1;
        color: #d1d5db;

        &:active {
            color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
        }
    }
}

.sidebar__footer {
    padding: 16px;
    border-top: 1px solid #e5e7eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 10px;
}

.user-avatar {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
}

.user-name {
    font-size: 14px;
    font-weight: 500;
    color: #374151;
}

.logout-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #9ca3af;
    padding: 6px;
    border-radius: 6px;
    transition: all 0.15s;

    &:hover {
        color: #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }
}

// Main Content
.main {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    min-width: 0;
    height: 100%;
    overflow: hidden;
    background: #ffffff;
}

.mobile-header {
    padding: 12px 16px;
    background: white;
    border-bottom: 1px solid #e5e7eb;
    display: none;
    align-items: center;
    justify-content: space-between;

    .header-title {
        font-size: 17px;
        font-weight: 600;
        color: #111827;
    }

    @media (max-width: 768px) {
        display: flex;
    }
}

.menu-btn,
.new-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #374151;
    padding: 8px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;

    &:hover {
        background: #f3f4f6;
    }

    &:active {
        background: #e5e7eb;
    }

    svg {
        display: block;
    }
}

// Chat Container
.chat-container {
    flex: 1;
    overflow-y: auto;
    padding: 0 20px;
    scroll-behavior: smooth;
    background: #ffffff;

    &::-webkit-scrollbar {
        width: 6px;
    }

    &::-webkit-scrollbar-thumb {
        background: #e5e7eb;
        border-radius: 6px;
    }

    @media (max-width: 768px) {
        padding: 0 12px;
        padding-bottom: 100px; // Space for fixed input
    }
}

.chat-messages {
    max-width: 800px;
    margin: 0 auto;
    padding-bottom: 20px;

    @media (max-width: 768px) {
        padding-bottom: 10px;
    }
}

.history-toggle {
    text-align: center;
    color: #6b7280;
    font-size: 13px;
    margin: 16px 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 16px;
    background: #f3f4f6;
    border-radius: 20px;
    width: fit-content;
    margin-left: auto;
    margin-right: auto;
    transition: all 0.15s;

    &:hover {
        background: #e5e7eb;
        color: #374151;
    }
}

// Input Area
.input-area {
    padding: 16px 20px;
    background: #ffffff;
    border-top: 1px solid #f0f0f0;
    flex-shrink: 0;

    @media (max-width: 768px) {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 12px 16px;
        padding-bottom: calc(12px + env(safe-area-inset-bottom));
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-top: 1px solid rgba(0, 0, 0, 0.05);
        z-index: 100;
    }
}

.input-wrapper {
    max-width: 800px;
    margin: 0 auto;
    display: flex;
    gap: 12px;
    align-items: flex-end;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 12px 16px;
    transition: all 0.2s;

    &:focus-within {
        border-color: #667eea;
        background: #ffffff;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    @media (max-width: 768px) {
        padding: 10px 14px;
        border-radius: 24px;
    }
}

textarea {
    flex: 1;
    border: none;
    resize: none;
    outline: none;
    padding: 4px 0;
    font-size: 15px;
    line-height: 1.5;
    background: transparent;
    color: #1f2937;
    max-height: 120px;

    &::placeholder {
        color: #9ca3af;
    }

    @media (max-width: 768px) {
        font-size: 16px; // Prevent iOS zoom
    }
}

.send-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0;

    &:hover {
        transform: scale(1.05);
    }

    &:disabled {
        background: #d1d5db;
        cursor: not-allowed;
        transform: none;
    }

    &.stop-btn {
        background: #ef4444;
    }

    @media (max-width: 768px) {
        width: 36px;
        height: 36px;
        border-radius: 50%;
    }
}
</style>
