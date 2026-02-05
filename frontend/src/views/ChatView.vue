<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useThemeStore } from '@/stores/theme';
import ChatMessage from '@/components/ChatMessage.vue';
import DigitalHuman from '@/components/DigitalHuman.vue';
import {
    Plus, MessageSquare, Trash2, LogOut,
    Menu, ChevronDown, ChevronUp, Send, Square,
    X, Sparkles, Sun, Moon, Mic, MicOff, User2
} from 'lucide-vue-next';

// 数字人状态
const showDigitalHuman = ref(false);
const isSpeaking = ref(false);
const currentAudioElement = ref<HTMLAudioElement | null>(null);

const router = useRouter();
const authStore = useAuthStore();
const themeStore = useThemeStore();

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

// Speech Recognition (STT) - 使用后端 FunASR
const isListening = ref(false);
const speechSupported = ref(true);  // 后端 STT 始终支持
const isProcessing = ref(false);  // 识别处理中
const recordingTime = ref(0);  // 录音时长（秒）
let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];
let recordingTimer: ReturnType<typeof setInterval> | null = null;

// 将音频转换为 PCM 格式 (16kHz, 16bit, 单声道)
const convertToPCM = async (audioBlob: Blob): Promise<ArrayBuffer> => {
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

    // 获取单声道数据
    const channelData = audioBuffer.getChannelData(0);

    // 重采样到 16kHz（如果需要）
    const sampleRate = audioBuffer.sampleRate;
    let samples = channelData;

    if (sampleRate !== 16000) {
        const ratio = sampleRate / 16000;
        const newLength = Math.round(channelData.length / ratio);
        samples = new Float32Array(newLength);
        for (let i = 0; i < newLength; i++) {
            samples[i] = channelData[Math.round(i * ratio)];
        }
    }

    // 转换为 16-bit PCM
    const pcmData = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    await audioContext.close();
    return pcmData.buffer;
};

const toggleListening = async () => {
    if (isListening.value) {
        // 停止录音
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        if (recordingTimer) {
            clearInterval(recordingTimer);
            recordingTimer = null;
        }
        isListening.value = false;
    } else {
        // 开始录音
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            audioChunks = [];
            recordingTime.value = 0;
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            // 录音计时器
            recordingTimer = setInterval(() => {
                recordingTime.value++;
            }, 1000);

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                // 停止所有音轨
                stream.getTracks().forEach(track => track.stop());

                if (audioChunks.length === 0) return;

                isProcessing.value = true;

                // 合并音频数据
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

                try {
                    // 转换为 PCM 格式
                    const pcmBuffer = await convertToPCM(audioBlob);

                    // 分块编码避免栈溢出
                    const bytes = new Uint8Array(pcmBuffer);
                    let binary = '';
                    const chunkSize = 8192;
                    for (let i = 0; i < bytes.length; i += chunkSize) {
                        const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
                        binary += String.fromCharCode.apply(null, Array.from(chunk));
                    }
                    const base64Audio = btoa(binary);

                    // 调用后端 STT API
                    const response = await fetch('/api/stt/recognize', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            audio: base64Audio,
                            format: 'pcm',
                            sample_rate: 16000
                        })
                    });

                    const result = await response.json();
                    if (result.success && result.text) {
                        userInput.value = result.text;
                    }
                } catch (e: any) {
                    console.error('语音识别失败:', e);
                } finally {
                    isProcessing.value = false;
                }
            };

            mediaRecorder.start(1000);  // 每秒触发一次 ondataavailable
            isListening.value = true;
        } catch (e: any) {
            console.error('麦克风访问失败:', e);
            isListening.value = false;
        }
    }
};

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
        const res = await fetch('/api/chat/sessions', {
            headers: authStore.getAuthHeaders()
        });
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
        const res = await fetch(`/api/chat/session/${id}`, {
            method: 'DELETE',
            headers: authStore.getAuthHeaders()
        });
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
        const res = await fetch(`/api/chat/history?session_id=${sessionId.value}`, {
            headers: authStore.getAuthHeaders()
        });
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
            headers: authStore.getAuthHeaders(),
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

// 直接发送消息（用于重新生成和编辑）
const sendMessageDirect = async (text: string, replaceLastAi = false) => {
    if (!text.trim() || isLoading.value) return;

    isLoading.value = true;
    abortController.value = new AbortController();

    await nextTick();
    scrollToBottom();

    // 如果是替换最后一条 AI 消息（重新生成）
    let aiMsgIndex: number = messages.value.length;
    if (replaceLastAi) {
        // 找到最后一条 AI 消息并重置它
        let found = false;
        for (let i = messages.value.length - 1; i >= 0; i--) {
            if (messages.value[i].role === 'ai') {
                aiMsgIndex = i;
                messages.value[i] = { role: 'ai', text: '', elapsed: 0 };
                found = true;
                break;
            }
        }
        if (!found) {
            // 没找到 AI 消息，添加新的
            messages.value.push({ role: 'ai', text: '', elapsed: 0 });
        }
    } else {
        // 添加新的 AI 消息
        aiMsgIndex = messages.value.length;
        messages.value.push({ role: 'ai', text: '', elapsed: 0 });
    }

    const startTime = Date.now();

    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: authStore.getAuthHeaders(),
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

// 重新生成 AI 回复
const regenerateMessage = (msgIndex: number) => {
    // 找到这条 AI 消息之前的用户消息
    let userText = '';
    for (let i = msgIndex - 1; i >= 0; i--) {
        if (messages.value[i].role === 'user') {
            userText = messages.value[i].text;
            break;
        }
    }
    if (userText) {
        sendMessageDirect(userText, true);
    }
};

// 编辑用户消息
const editMessage = (msgIndex: number, newText: string) => {
    // 更新用户消息
    messages.value[msgIndex].text = newText;
    messages.value[msgIndex].timestamp = new Date().toISOString();

    // 删除这条消息之后的所有消息（包括 AI 回复）
    messages.value = messages.value.slice(0, msgIndex + 1);

    // 发送新消息获取 AI 回复
    sendMessageDirect(newText);
};

// 获取消息在 messages 数组中的真实索引
const getRealIndex = (displayIndex: number) => {
    if (showAllMessages.value || messages.value.length <= RECENT_MESSAGE_COUNT) {
        return displayIndex;
    }
    const offset = messages.value.length - RECENT_MESSAGE_COUNT;
    return displayIndex + offset;
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
                <div class="footer-actions">
                    <button class="theme-btn" @click="themeStore.toggleTheme"
                        :title="themeStore.theme === 'dark' ? '切换浅色' : '切换深色'">
                        <Sun v-if="themeStore.theme === 'dark'" :size="18" />
                        <Moon v-else :size="18" />
                    </button>
                    <button class="logout-btn" @click="handleLogout" title="退出登录">
                        <LogOut :size="18" />
                    </button>
                </div>
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

            <!-- Digital Human -->
            <div v-if="showDigitalHuman" class="digital-human-container">
                <DigitalHuman :is-speaking="isSpeaking" :audio-element="currentAudioElement" />
                <button class="digital-human-toggle digital-human-toggle--close" @click="showDigitalHuman = false">
                    <X :size="16" />
                </button>
            </div>

            <!-- Digital Human Toggle Button -->
            <button v-if="!showDigitalHuman" class="digital-human-toggle" @click="showDigitalHuman = true"
                title="显示数字人">
                <User2 :size="20" />
            </button>

            <!-- Messages -->
            <div ref="chatContainer" class="messages-container" :class="{ 'has-digital-human': showDigitalHuman }">
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
                        :text="msg.text" :message-id="`${sessionId}-${getRealIndex(index)}`" :sources="msg.sources"
                        :timestamp="msg.timestamp" :elapsed="msg.elapsed"
                        :loading="isLoading && index === displayedMessages.length - 1 && msg.role === 'ai' && !msg.text"
                        :is-last="index === displayedMessages.length - 1"
                        :can-regenerate="msg.role === 'ai' && index === displayedMessages.length - 1 && !isLoading"
                        @regenerate="regenerateMessage(getRealIndex(index))"
                        @edit="(newText) => editMessage(getRealIndex(index), newText)"
                        @speaking="(val) => isSpeaking = val" @audio-element="(el) => currentAudioElement = el" />
                </div>
            </div>

            <!-- Input Area -->
            <div class="input-area">
                <!-- Recording / Processing Overlay -->
                <div v-if="isListening || isProcessing" class="voice-overlay" @click="isListening && toggleListening()">
                    <div class="voice-modal" @click.stop>
                        <div v-if="isListening" class="voice-waves">
                            <span></span><span></span><span></span><span></span><span></span>
                        </div>
                        <div v-else class="voice-processing">
                            <div class="spinner"></div>
                        </div>
                        <p class="voice-text">
                            {{ isProcessing ? '识别中...' : `${recordingTime}"` }}
                        </p>
                        <button v-if="isListening" class="voice-stop-btn" @click="toggleListening">
                            停止录音
                        </button>
                        <p class="voice-hint" v-else>请稍候...</p>
                    </div>
                </div>
                <div class="input-container">
                    <textarea v-model="userInput" :disabled="isLoading || isListening || isProcessing" rows="1"
                        :placeholder="isListening ? '正在聆听...' : '输入消息...'"
                        @keydown.enter.exact.prevent="sendMessage"></textarea>
                    <!-- Mic Button -->
                    <button v-if="speechSupported" class="mic-btn"
                        :class="{ 'mic-btn--active': isListening, 'mic-btn--processing': isProcessing }"
                        @click="toggleListening" :disabled="isLoading || isProcessing">
                        <MicOff v-if="isListening" :size="20" />
                        <Mic v-else :size="20" />
                    </button>
                    <!-- Send Button -->
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
// Reset & Base
.app-container {
    display: flex;
    height: 100vh;
    width: 100vw;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow: hidden;
    transition: background-color 0.3s ease, color 0.3s ease;
}

// Overlay
.overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    z-index: 40;
}

// Digital Human
.digital-human-container {
    position: relative;
    padding: 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);

    @media (max-width: 768px) {
        padding: 12px;
    }
}

.digital-human-toggle {
    position: absolute;
    top: 80px;
    right: 16px;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: all 0.2s;

    &:hover {
        color: var(--text-primary);
        border-color: var(--primary);
        transform: scale(1.05);
    }

    &--close {
        position: absolute;
        top: 8px;
        right: 8px;
        width: 32px;
        height: 32px;
        background: rgba(0, 0, 0, 0.4);
        border: none;
        color: white;

        &:hover {
            background: rgba(0, 0, 0, 0.6);
        }
    }

    @media (max-width: 768px) {
        top: 140px;
        right: 12px;
        width: 40px;
        height: 40px;
    }
}

.messages-container.has-digital-human {
    height: calc(100% - 316px - 120px); // 减去数字人高度

    @media (max-width: 768px) {
        height: calc(100% - 300px - 160px);
    }
}

// Sidebar
.sidebar {
    width: 260px;
    height: 100%;
    background: var(--bg-secondary);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    border-right: 1px solid var(--border-color);

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
    border-bottom: 1px solid var(--border-color);
}

.logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
}

.logo-icon {
    color: var(--primary);
}

.close-btn {
    display: none;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    transition: all 0.15s;

    &:hover {
        color: var(--text-primary);
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
        background: var(--border-color);
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
    border: 1px dashed var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 16px;

    &:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: var(--text-secondary);
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
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 8px 12px;
}

.sessions-empty {
    text-align: center;
    color: var(--text-secondary);
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
    color: var(--text-secondary);
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
    color: var(--text-secondary);
    margin-top: 2px;
}

.session-delete {
    opacity: 0;
    background: none;
    border: none;
    color: var(--text-secondary);
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
    border-top: 1px solid var(--border-color);
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
    background: var(--primary);
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

.footer-actions {
    display: flex;
    align-items: center;
    gap: 4px;
}

.theme-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 6px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;

    &:hover {
        color: var(--text-primary);
        background: rgba(255, 255, 255, 0.1);
    }
}

.logout-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 6px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
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
    background: var(--bg-primary);
}

.mobile-header {
    display: none;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);

    @media (max-width: 768px) {
        display: flex;
    }
}

.icon-btn {
    background: none;
    border: none;
    color: var(--text-primary);
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
        background: var(--border-color);
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
    border: 1px solid var(--border-color);
    border-radius: 20px;
    color: var(--text-secondary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
    width: fit-content;

    &:hover {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text-primary);
    }
}

// Input Area
.input-area {
    padding: 16px;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-color);

    @media (max-width: 768px) {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding-bottom: calc(16px + env(safe-area-inset-bottom));
        z-index: 30;
    }
}

.voice-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
}

.voice-modal {
    background: rgba(40, 40, 40, 0.95);
    border-radius: 16px;
    padding: 32px 48px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.voice-waves {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 50px;
    margin-bottom: 16px;

    span {
        display: block;
        width: 4px;
        height: 20px;
        background: linear-gradient(180deg, #10b981, #34d399);
        border-radius: 2px;
        animation: wave 0.8s ease-in-out infinite;

        &:nth-child(1) {
            animation-delay: 0s;
            height: 20px;
        }

        &:nth-child(2) {
            animation-delay: 0.1s;
            height: 35px;
        }

        &:nth-child(3) {
            animation-delay: 0.2s;
            height: 50px;
        }

        &:nth-child(4) {
            animation-delay: 0.1s;
            height: 35px;
        }

        &:nth-child(5) {
            animation-delay: 0s;
            height: 20px;
        }
    }
}

@keyframes wave {

    0%,
    100% {
        transform: scaleY(0.5);
    }

    50% {
        transform: scaleY(1);
    }
}

.voice-processing {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 50px;
    margin-bottom: 16px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255, 255, 255, 0.2);
    border-top-color: #10b981;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.voice-text {
    color: #fff;
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 16px;
}

.voice-stop-btn {
    background: #ef4444;
    border: none;
    color: white;
    padding: 12px 32px;
    border-radius: 24px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;

    &:hover {
        background: #dc2626;
    }

    &:active {
        transform: scale(0.95);
    }
}

.voice-hint {
    color: rgba(255, 255, 255, 0.6);
    font-size: 13px;
    margin: 16px 0 0;
}

.input-container {
    max-width: 800px;
    margin: 0 auto;
    display: flex;
    align-items: flex-end;
    gap: 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 12px 16px;
    transition: all 0.2s;

    &:focus-within {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(var(--primary), 0.2);
    }
}

textarea {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    color: var(--text-primary);
    font-size: 15px;
    line-height: 1.5;
    max-height: 150px;
    font-family: inherit;

    &::placeholder {
        color: var(--text-secondary);
    }

    @media (max-width: 768px) {
        font-size: 16px;
    }
}

.send-btn {
    width: 36px;
    height: 36px;
    background: var(--primary);
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
        background: var(--primary)-hover;
    }

    &:disabled {
        background: var(--border-color);
        color: var(--text-secondary);
        cursor: not-allowed;
    }

    &--stop {
        background: #ef4444;

        &:hover {
            background: #dc2626;
        }
    }
}

.mic-btn {
    width: 36px;
    height: 36px;
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.15s;

    &:hover:not(:disabled) {
        color: var(--text-primary);
        border-color: var(--text-secondary);
    }

    &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    &--active {
        background: #10b981;
        border-color: #10b981;
        color: white;
        animation: pulse 1.5s infinite;
    }

    &--processing {
        background: #6366f1;
        border-color: #6366f1;
        color: white;
    }
}

@keyframes pulse {

    0%,
    100% {
        opacity: 1;
    }

    50% {
        opacity: 0.6;
    }
}

.input-hint {
    max-width: 800px;
    margin: 8px auto 0;
    text-align: center;
    font-size: 11px;
    color: var(--text-secondary);
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
