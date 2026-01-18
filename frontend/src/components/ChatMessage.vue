<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import { Bot, User, FileText, Wrench, Clock, Copy, Check, RefreshCw, Pencil, X, Send } from 'lucide-vue-next';

interface Source {
    type?: string;
    name?: string;
    args?: string;
    file_name?: string;
    page?: number | string;
}

const props = defineProps<{
    role: 'user' | 'ai';
    text: string;
    loading?: boolean;
    sources?: Source[];
    timestamp?: string;
    elapsed?: number;
    isLast?: boolean;
    canRegenerate?: boolean;
}>();

const emit = defineEmits<{
    (e: 'regenerate'): void;
    (e: 'edit', newText: string): void;
}>();

const copied = ref(false);
const isEditing = ref(false);
const editText = ref('');
const editTextarea = ref<HTMLTextAreaElement | null>(null);

const formattedTime = computed(() => {
    if (!props.timestamp) return '';
    const date = new Date(props.timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
});

const md: MarkdownIt = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: true,
    highlight: function (str: string, lang: string): string {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return `<pre class="code-block"><div class="code-header"><span class="code-lang">${lang}</span></div><code class="hljs">${hljs.highlight(str, { language: lang }).value}</code></pre>`;
            } catch (__) { }
        }
        return `<pre class="code-block"><code class="hljs">${md.utils.escapeHtml(str)}</code></pre>`;
    }
});

const renderedText = computed(() => {
    return md.render(props.text || '');
});

const copyMessage = async () => {
    try {
        // 优先使用现代 Clipboard API
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(props.text);
        } else {
            // 回退方案：使用 execCommand
            const textarea = document.createElement('textarea');
            textarea.value = props.text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
        }
        copied.value = true;
        setTimeout(() => copied.value = false, 2000);
    } catch (e) {
        console.error('Copy failed:', e);
    }
};

const startEdit = async () => {
    editText.value = props.text;
    isEditing.value = true;
    await nextTick();
    if (editTextarea.value) {
        editTextarea.value.focus();
        editTextarea.value.style.height = 'auto';
        editTextarea.value.style.height = editTextarea.value.scrollHeight + 'px';
    }
};

const cancelEdit = () => {
    isEditing.value = false;
    editText.value = '';
};

const submitEdit = () => {
    if (editText.value.trim() && editText.value !== props.text) {
        emit('edit', editText.value.trim());
    }
    isEditing.value = false;
};

const handleRegenerate = () => {
    emit('regenerate');
};

const autoResize = (e: Event) => {
    const target = e.target as HTMLTextAreaElement;
    target.style.height = 'auto';
    target.style.height = target.scrollHeight + 'px';
};
</script>

<template>
    <div class="message" :class="[`message--${role}`]">
        <div class="message-inner">
            <!-- Avatar -->
            <div class="avatar" :class="[`avatar--${role}`]">
                <Bot v-if="role === 'ai'" :size="20" />
                <User v-else :size="18" />
            </div>

            <!-- Content -->
            <div class="content">
                <div class="role-name">{{ role === 'ai' ? 'AI' : '你' }}</div>

                <!-- Editing Mode -->
                <div v-if="isEditing && role === 'user'" class="edit-container">
                    <textarea ref="editTextarea" v-model="editText" class="edit-textarea" @input="autoResize"
                        @keydown.enter.exact.prevent="submitEdit" @keydown.escape="cancelEdit"></textarea>
                    <div class="edit-actions">
                        <button class="edit-btn edit-btn--cancel" @click="cancelEdit" title="取消">
                            <X :size="16" />
                            <span>取消</span>
                        </button>
                        <button class="edit-btn edit-btn--submit" @click="submitEdit" title="发送">
                            <Send :size="16" />
                            <span>发送</span>
                        </button>
                    </div>
                </div>

                <!-- Normal Display -->
                <template v-else>
                    <div class="text-content">
                        <div v-if="role === 'ai'" class="markdown-body" v-html="renderedText"></div>
                        <div v-else class="plain-text">{{ text }}</div>
                        <span v-if="loading" class="typing-cursor"></span>
                    </div>

                    <!-- Sources -->
                    <div v-if="role === 'ai' && sources && sources.length > 0" class="sources">
                        <div v-for="(source, idx) in sources" :key="idx" class="source-tag"
                            :class="{ 'source-tag--tool': source.type === 'tool' }">
                            <Wrench v-if="source.type === 'tool'" :size="12" />
                            <FileText v-else :size="12" />
                            <span v-if="source.type === 'tool'">{{ source.name }}</span>
                            <span v-else>{{ source.file_name }}<span v-if="source.page" class="page">p{{ source.page
                            }}</span></span>
                        </div>
                    </div>

                    <!-- Footer for AI messages -->
                    <div v-if="role === 'ai' && !loading" class="message-footer">
                        <div class="meta">
                            <span v-if="elapsed" class="meta-item">
                                <Clock :size="12" />
                                {{ (elapsed / 1000).toFixed(1) }}s
                            </span>
                            <span v-if="formattedTime" class="meta-item">{{ formattedTime }}</span>
                        </div>
                        <div class="actions">
                            <button v-if="canRegenerate" class="action-btn" @click="handleRegenerate" title="重新生成">
                                <RefreshCw :size="14" />
                            </button>
                            <button class="action-btn" @click="copyMessage" :title="copied ? '已复制' : '复制'">
                                <Check v-if="copied" :size="14" />
                                <Copy v-else :size="14" />
                            </button>
                        </div>
                    </div>

                    <!-- Footer for User messages -->
                    <div v-if="role === 'user'" class="message-footer message-footer--user">
                        <div class="meta">
                            <span v-if="formattedTime" class="meta-item">{{ formattedTime }}</span>
                        </div>
                        <div class="actions">
                            <button class="action-btn" @click="startEdit" title="编辑">
                                <Pencil :size="14" />
                            </button>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
.message {
    padding: 24px 0;

    &--user {
        background: var(--bg-primary);
    }

    &--ai {
        background: var(--bg-tertiary);
    }
}

.message-inner {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 16px;
    display: flex;
    gap: 16px;
}

.avatar {
    width: 32px;
    height: 32px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;

    &--ai {
        background: var(--primary);
        color: white;
    }

    &--user {
        background: #5436da;
        color: white;
    }
}

.content {
    flex: 1;
    min-width: 0;
}

.role-name {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--text-primary);
}

.text-content {
    font-size: 15px;
    line-height: 1.75;
    color: var(--text-primary);
}

.plain-text {
    white-space: pre-wrap;
    word-break: break-word;
}

.typing-cursor {
    display: inline-block;
    width: 8px;
    height: 20px;
    background: var(--primary);
    margin-left: 4px;
    border-radius: 2px;
    animation: blink 1s ease-in-out infinite;
    vertical-align: text-bottom;
}

@keyframes blink {

    0%,
    50% {
        opacity: 1;
    }

    51%,
    100% {
        opacity: 0.3;
    }
}

// Edit Mode
.edit-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.edit-textarea {
    width: 100%;
    min-height: 60px;
    max-height: 300px;
    padding: 12px 14px;
    background: var(--bg-input, var(--bg-primary));
    border: 2px solid var(--primary);
    border-radius: 10px;
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-primary);
    resize: none;
    font-family: inherit;
    box-sizing: border-box;

    &:focus {
        outline: none;
    }
}

.edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}

.edit-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;

    &--cancel {
        background: transparent;
        border: 1px solid var(--border-color);
        color: var(--text-secondary);

        &:hover {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
        }
    }

    &--submit {
        background: var(--primary);
        border: none;
        color: white;

        &:hover {
            background: var(--primary-hover);
        }
    }
}

// Sources
.sources {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
}

.source-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-secondary);

    &--tool {
        background: rgba(16, 163, 127, 0.1);
        border-color: rgba(16, 163, 127, 0.3);
        color: var(--primary);
    }

    .page {
        margin-left: 4px;
        opacity: 0.7;
    }
}

// Footer
.message-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);

    &--user {
        opacity: 0;
        transition: opacity 0.15s;
    }
}

.message:hover .message-footer--user {
    opacity: 1;
}

.meta {
    display: flex;
    align-items: center;
    gap: 16px;
}

.meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--text-secondary);
}

.actions {
    display: flex;
    align-items: center;
    gap: 4px;
}

.action-btn {
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

// Markdown Styles
.markdown-body {
    color: var(--text-primary);

    :deep(p) {
        margin: 0 0 16px;

        &:last-child {
            margin-bottom: 0;
        }
    }

    :deep(h1),
    :deep(h2),
    :deep(h3),
    :deep(h4) {
        margin: 24px 0 12px;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.4;

        &:first-child {
            margin-top: 0;
        }
    }

    :deep(h1) {
        font-size: 1.5em;
    }

    :deep(h2) {
        font-size: 1.3em;
    }

    :deep(h3) {
        font-size: 1.15em;
    }

    :deep(.code-block) {
        background: #0d0d0d;
        border-radius: 8px;
        margin: 16px 0;
        overflow: hidden;

        .code-header {
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .code-lang {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: lowercase;
        }

        code {
            display: block;
            padding: 16px;
            overflow-x: auto;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.6;
        }
    }

    :deep(code) {
        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        background: rgba(255, 255, 255, 0.1);
        color: #f97583;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
    }

    :deep(pre code) {
        background: transparent;
        color: inherit;
        padding: 0;
    }

    :deep(ul),
    :deep(ol) {
        margin: 12px 0;
        padding-left: 24px;
    }

    :deep(li) {
        margin: 6px 0;
    }

    :deep(strong) {
        font-weight: 600;
        color: var(--text-primary);
    }

    :deep(a) {
        color: #58a6ff;
        text-decoration: none;

        &:hover {
            text-decoration: underline;
        }
    }

    :deep(blockquote) {
        border-left: 4px solid var(--border-color);
        margin: 16px 0;
        padding-left: 16px;
        color: var(--text-secondary);
        font-style: italic;
    }

    :deep(table) {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;
        font-size: 14px;
    }

    :deep(th),
    :deep(td) {
        padding: 10px 14px;
        border: 1px solid var(--border-color);
        text-align: left;
    }

    :deep(th) {
        background: rgba(255, 255, 255, 0.05);
        font-weight: 600;
    }

    :deep(hr) {
        border: none;
        border-top: 1px solid var(--border-color);
        margin: 24px 0;
    }
}

// Mobile
@media (max-width: 768px) {
    .message {
        padding: 16px 0;
    }

    .message-inner {
        gap: 12px;
        padding: 0 12px;
    }

    .avatar {
        width: 28px;
        height: 28px;
    }

    .message-footer--user {
        opacity: 1;
    }
}
</style>
