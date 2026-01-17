<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import ChatMessage from '@/components/ChatMessage.vue';
import {
    Plus, MessageSquare, Trash2, LogOut,
    Menu, ChevronDown, ChevronUp, Send, Square,
    X, Sparkles
} from 'lucide-vue-next';

const router = useRouter();
const authStore = useAuthStore();

interface Message {
    role: 'user' | 'ai';
    text: string;
    sources?: any[];
    timestamp?: string;
    elapsed?: number;
}

const defaultMessage: Message = {
    role: 'ai',
    text: '你好！我是你的 AI 助手。有什么我可以帮助你的吗？'
};

const isMobileMenuOpen = ref(false);
const sessionId = ref('');
const messages = ref<Message[]>([defaultMessage]);
const userInput = ref('');
const isLoading = ref(false);
const chatContainer = ref<HTMLElement | null>(null);
const abortController = ref<AbortController | null>(null);

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

interface Session {
    id: string;
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
                    text: h.text || '',
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
                messages: [{ role: 'user', text: text }],
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
                    if (data.text) {
                        messages.value[aiMsgIndex].text += data.text;
                    } else if (data.sources) {
                        messages.value[aiMsgIndex].sources = data.sources;
                    } else if (data.type === 'content') {
                        messages.value[aiMsgIndex].text += data.content;
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
    <div class="app-container">
        <!-- Overlay -->
        <Transition name="fade">
            <div v-if="isMobileMenuOpen" class="overlay" @click="isMobileMenuOpen = false"></div>
        </Transition>

        <!-- Sidebar -->
        <aside class="sidebar" :class="{ 'sidebar--open': isMobileMenuOpen }">
            <div class="sidebar-header">
                <div class="logo">
                    <Sparkles class="logo-icon" :size="24" />
                    <span>AI Chat</span>
                </div>
                <button class="close-btn" @click="isMobileMenuOpen = false">
                    <X :size="20" />
                </button>
            </div>

            <div class="sidebar-content">
                <button class="new-chat-btn" @click="createNewSession">
                    <Plus :size="18" />
                    <span>新对话</span>
                </button>

                <div class="sessions-list">
                    <div class="sessions-label">历史记录</div>
                    <div v-if="sessions.length === 0" class="sessions-empty">
                        暂无对话
                    </div>
                    <div v-for="session in sessions" :key="session.id" class="session-item"
                        :class="{ 'session-item--active': session.id === sessionId }" @click="switchSession(session)">
                        <MessageSquare :size="16" class="session-icon" />
                        <div class="session-content">
                            <div class="session-title">{{ session.title }}</div>
                            <div class="session-time">{{ formatTime(session.updated_at) }}</div>
                        </div>
                        <button class="session-delete" @click.stop="deleteSession(session.id)">
                            <Trash2 :size="14" />
                        </button>
                    </div>
                </div>
            </div>

            <div class="sidebar-footer">
                <div class="user-info">
                    <div class="user-avatar">
                        {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
                    </div>
                    <span class="user-name">{{ authStore.user?.username || 'User' }}</span>
                </div>
                <button class="logout-btn" @click="handleLogout" title="退出登录">
                    <LogOut :size="18" />
                </button>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Mobile Header -->
            <header class="mobile-header">
                <button class="icon-btn" @click="isMobileMenuOpen = true">
                    <Menu :size="22" />
                </button>
                <h1 class="page-title">AI Chat</h1>
                <button class="icon-btn" @click="createNewSession">
                    <Plus :size="22" />
                </button>
            </header>

            <!-- Messages -->
            <div ref="chatContainer" class="messages-container">
                <div class="messages-wrapper">
                    <!-- History Toggle -->
                    <div v-if="hiddenMessageCount > 0" class="history-toggle" @click="showAllMessages = true">
                        <ChevronDown :size="16" />
                        <span>展开 {{ hiddenMessageCount }} 条历史消息</span>
                    </div>
                    <div v-if="showAllMessages && messages.length > RECENT_MESSAGE_COUNT" class="history-toggle"
                        @click="showAllMessages = false">
                        <ChevronUp :size="16" />
                        <span>收起历史消息</span>
                    </div>

                    <!-- Messages -->
                    <ChatMessage v-for="(msg, index) in displayedMessages" :key="index" :role="msg.role"
                        :text="msg.text" :sources="msg.sources" :timestamp="msg.timestamp" :elapsed="msg.elapsed"
                        :loading="isLoading && index === displayedMessages.length - 1 && msg.role === 'ai' && !msg.text" />
                </div>
            </div>

            <!-- Input Area -->
            <div class="input-area">
                <div class="input-container">
                    <textarea v-model="userInput" :disabled="isLoading" rows="1" placeholder="输入消息..."
                        @keydown.enter.exact.prevent="sendMessage"></textarea>
                    <button v-if="isLoading" class="send-btn send-btn--stop" @click="stopGeneration">
                        <Square :size="18" />
                    </button>
                    <button v-else class="send-btn" :disabled="!userInput.trim()" @click="sendMessage">
                        <Send :size="18" />
                    </button>
                </div>
                <p class="input-hint">AI 可能会犯错，请核实重要信息</p>
            </div>
        </main>
    </div>
</template>

<style scoped lang="scss">
// Variables
$primary: #10a37f;
$primary-hover: #0d8c6d;
$bg-dark: #202123;
$bg-darker: #171717;
$bg-light: #343541;
$text-primary: #ececf1;
$text-secondary: #8e8ea0;
$border-color: #4e4f60;

// Reset & Base
.app-container {
    display: flex;
    height: 100vh;
    width: 100vw;
    background: $bg-light;
    color: $text-primary;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow: hidden;
}

// Overlay
.overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    z-index: 40;
}

// Sidebar
.sidebar {
    width: 260px;
    height: 100%;
    background: $bg-dark;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    border-right: 1px solid $border-color;

    @media (max-width: 768px) {
        position: fixed;
        left: 0;
        top: 0;
        bottom: 0;
        z-index: 50;
        transform: translateX(-100%);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

        &--open {
            transform: translateX(0);
        }
    }
}

.sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid $border-color;
}

.logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
}

.logo-icon {
    color: $primary;
}

.close-btn {
    display: none;
    background: none;
    border: none;
    color: $text-secondary;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    transition: all 0.15s;

    &:hover {
        color: $text-primary;
        background: rgba(255, 255, 255, 0.1);
    }

    @media (max-width: 768px) {
        display: flex;
    }
}

.sidebar-content {
    flex: 1;
    overflow-y: auto;
    padding: 12px;

    &::-webkit-scrollbar {
        width: 4px;
    }

    &::-webkit-scrollbar-thumb {
        background: $border-color;
        border-radius: 4px;
    }
}

.new-chat-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 16px;
    background: transparent;
    border: 1px dashed $border-color;
    border-radius: 8px;
    color: $text-primary;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 16px;

    &:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: $text-secondary;
    }
}

.sessions-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.sessions-label {
    font-size: 11px;
    font-weight: 600;
    color: $text-secondary;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 8px 12px;
}

.sessions-empty {
    text-align: center;
    color: $text-secondary;
    font-size: 13px;
    padding: 20px;
}

.session-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s;

    &:hover {
        background: rgba(255, 255, 255, 0.05);

        .session-delete {
            opacity: 1;
        }
    }

    &--active {
        background: rgba(255, 255, 255, 0.1);
    }
}

.session-icon {
    flex-shrink: 0;
    color: $text-secondary;
}

.session-content {
    flex: 1;
    min-width: 0;
}

.session-title {
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.session-time {
    font-size: 11px;
    color: $text-secondary;
    margin-top: 2px;
}

.session-delete {
    opacity: 0;
    background: none;
    border: none;
    color: $text-secondary;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.15s;

    &:hover {
        color: #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }

    @media (max-width: 768px) {
        opacity: 1;
    }
}

.sidebar-footer {
    padding: 12px 16px;
    border-top: 1px solid $border-color;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 10px;
}

.user-avatar {
    width: 32px;
    height: 32px;
    background: $primary;
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
}

.logout-btn {
    background: none;
    border: none;
    color: $text-secondary;
    cursor: pointer;
    padding: 6px;
    border-radius: 6px;
    transition: all 0.15s;

    &:hover {
        color: #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }
}

// Main Content
.main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100%;
    background: $bg-light;
}

.mobile-header {
    display: none;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: $bg-dark;
    border-bottom: 1px solid $border-color;

    @media (max-width: 768px) {
        display: flex;
    }
}

.icon-btn {
    background: none;
    border: none;
    color: $text-primary;
    cursor: pointer;
    padding: 8px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;

    &:hover {
        background: rgba(255, 255, 255, 0.1);
    }
}

.page-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0;
}

// Messages
.messages-container {
    flex: 1;
    overflow-y: auto;
    scroll-behavior: smooth;

    &::-webkit-scrollbar {
        width: 6px;
    }

    &::-webkit-scrollbar-thumb {
        background: $border-color;
        border-radius: 6px;
    }

    @media (max-width: 768px) {
        padding-bottom: 120px;
    }
}

.messages-wrapper {
    max-width: 800px;
    margin: 0 auto;
    padding: 24px 16px;
}

.history-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 20px;
    margin: 0 auto 24px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid $border-color;
    border-radius: 20px;
    color: $text-secondary;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
    width: fit-content;

    &:hover {
        background: rgba(255, 255, 255, 0.1);
        color: $text-primary;
    }
}

// Input Area
.input-area {
    padding: 16px;
    background: $bg-light;
    border-top: 1px solid $border-color;

    @media (max-width: 768px) {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding-bottom: calc(16px + env(safe-area-inset-bottom));
        z-index: 30;
    }
}

.input-container {
    max-width: 800px;
    margin: 0 auto;
    display: flex;
    align-items: flex-end;
    gap: 12px;
    background: $bg-dark;
    border: 1px solid $border-color;
    border-radius: 16px;
    padding: 12px 16px;
    transition: all 0.2s;

    &:focus-within {
        border-color: $primary;
        box-shadow: 0 0 0 2px rgba($primary, 0.2);
    }
}

textarea {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    color: $text-primary;
    font-size: 15px;
    line-height: 1.5;
    max-height: 150px;
    font-family: inherit;

    &::placeholder {
        color: $text-secondary;
    }

    @media (max-width: 768px) {
        font-size: 16px;
    }
}

.send-btn {
    width: 36px;
    height: 36px;
    background: $primary;
    border: none;
    border-radius: 8px;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.15s;

    &:hover:not(:disabled) {
        background: $primary-hover;
    }

    &:disabled {
        background: $border-color;
        color: $text-secondary;
        cursor: not-allowed;
    }

    &--stop {
        background: #ef4444;

        &:hover {
            background: #dc2626;
        }
    }
}

.input-hint {
    max-width: 800px;
    margin: 8px auto 0;
    text-align: center;
    font-size: 11px;
    color: $text-secondary;
}

// Animations
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>
