<script setup lang="ts">
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import { Bot, User, FileText, Wrench, Clock, Copy, Check } from 'lucide-vue-next';
import { ref } from 'vue';

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
}>();

const copied = ref(false);

const formattedTime = computed(() => {
    if (!props.timestamp) return '';
    const date = new Date(props.timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
});

const md = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: true,
    highlight: function (str, lang) {
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
        await navigator.clipboard.writeText(props.text);
        copied.value = true;
        setTimeout(() => copied.value = false, 2000);
    } catch (e) {
        console.error('Copy failed:', e);
    }
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

                <!-- Footer -->
                <div v-if="role === 'ai' && (elapsed || formattedTime)" class="message-footer">
                    <div class="meta">
                        <span v-if="elapsed" class="meta-item">
                            <Clock :size="12" />
                            {{ (elapsed / 1000).toFixed(1) }}s
                        </span>
                        <span v-if="formattedTime" class="meta-item">{{ formattedTime }}</span>
                    </div>
                    <button class="copy-btn" @click="copyMessage" :title="copied ? '已复制' : '复制'">
                        <Check v-if="copied" :size="14" />
                        <Copy v-else :size="14" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
$primary: #10a37f;
$bg-user: #343541;
$bg-ai: #444654;
$text-primary: #ececf1;
$text-secondary: #8e8ea0;
$border-color: #4e4f60;

.message {
    padding: 24px 0;

    &--user {
        background: $bg-user;
    }

    &--ai {
        background: $bg-ai;
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
        background: $primary;
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
    color: $text-primary;
}

.text-content {
    font-size: 15px;
    line-height: 1.75;
    color: $text-primary;
}

.plain-text {
    white-space: pre-wrap;
    word-break: break-word;
}

.typing-cursor {
    display: inline-block;
    width: 8px;
    height: 20px;
    background: $primary;
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
    border: 1px solid $border-color;
    border-radius: 6px;
    font-size: 12px;
    color: $text-secondary;

    &--tool {
        background: rgba($primary, 0.1);
        border-color: rgba($primary, 0.3);
        color: $primary;
    }

    .page {
        margin-left: 4px;
        opacity: 0.7;
    }
}

.message-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
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
    color: $text-secondary;
}

.copy-btn {
    background: none;
    border: none;
    color: $text-secondary;
    cursor: pointer;
    padding: 6px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;

    &:hover {
        color: $text-primary;
        background: rgba(255, 255, 255, 0.1);
    }
}

// Markdown Styles
.markdown-body {
    color: $text-primary;

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
        color: $text-primary;
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
            color: $text-secondary;
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
        color: $text-primary;
    }

    :deep(a) {
        color: #58a6ff;
        text-decoration: none;

        &:hover {
            text-decoration: underline;
        }
    }

    :deep(blockquote) {
        border-left: 4px solid $border-color;
        margin: 16px 0;
        padding-left: 16px;
        color: $text-secondary;
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
        border: 1px solid $border-color;
        text-align: left;
    }

    :deep(th) {
        background: rgba(255, 255, 255, 0.05);
        font-weight: 600;
    }

    :deep(hr) {
        border: none;
        border-top: 1px solid $border-color;
        margin: 24px 0;
    }
}
</style>
