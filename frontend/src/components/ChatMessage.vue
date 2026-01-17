<script setup lang="ts">
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import { UserFilled, Service, Document, Tools, Timer } from '@element-plus/icons-vue';

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
                return hljs.highlight(str, { language: lang }).value;
            } catch (__) { }
        }
        return '';
    }
});

const renderedText = computed(() => {
    return md.render(props.text || '');
});
</script>

<template>
    <div class="message" :class="[`message--${role}`]">
        <!-- Avatar -->
        <div class="message__avatar">
            <div v-if="role === 'ai'" class="avatar avatar--ai">
                <!-- Robot/AI icon -->
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="11" width="18" height="10" rx="2"/>
                    <circle cx="12" cy="5" r="2"/>
                    <path d="M12 7v4"/>
                    <line x1="8" y1="16" x2="8" y2="16"/>
                    <line x1="16" y1="16" x2="16" y2="16"/>
                </svg>
            </div>
            <div v-else class="avatar avatar--user">
                <!-- User icon -->
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                </svg>
            </div>
        </div>

        <!-- Content -->
        <div class="message__body">
            <div class="message__role">{{ role === 'ai' ? 'AI 助手' : '你' }}</div>
            
            <div class="message__content">
                <!-- AI: Markdown -->
                <div v-if="role === 'ai'" class="markdown-body" v-html="renderedText"></div>
                <!-- User: Plain text -->
                <div v-else class="plain-text">{{ text }}</div>
                <!-- Loading cursor -->
                <span v-if="loading" class="loading-cursor"></span>
            </div>

            <!-- Sources (AI only) -->
            <div v-if="role === 'ai' && sources && sources.length > 0" class="message__sources">
                <div v-for="(source, idx) in sources" :key="idx" 
                     class="source-tag" :class="{ 'source-tag--tool': source.type === 'tool' }">
                    <el-icon v-if="source.type === 'tool'" :size="12"><Tools /></el-icon>
                    <el-icon v-else :size="12"><Document /></el-icon>
                    <span v-if="source.type === 'tool'">{{ source.name }}</span>
                    <span v-else>{{ source.file_name }}<span v-if="source.page" class="page-num">p{{ source.page }}</span></span>
                </div>
            </div>

            <!-- Meta info -->
            <div class="message__meta">
                <span v-if="elapsed" class="meta-item">
                    <el-icon :size="12"><Timer /></el-icon>
                    {{ (elapsed / 1000).toFixed(1) }}s
                </span>
                <span v-if="formattedTime" class="meta-item">{{ formattedTime }}</span>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
.message {
    display: flex;
    gap: 16px;
    padding: 24px 0;
    border-bottom: 1px solid #f0f0f0;
    
    &:last-child {
        border-bottom: none;
    }
    
    &--ai {
        background: transparent;
    }
    
    &--user {
        background: #fafafa;
        margin: 0 -20px;
        padding-left: 20px;
        padding-right: 20px;
    }
    
    @media (max-width: 768px) {
        gap: 12px;
        padding: 16px 0;
        
        &--user {
            margin: 0 -12px;
            padding-left: 12px;
            padding-right: 12px;
        }
    }
}

.message__avatar {
    flex-shrink: 0;
}

.avatar {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    &--ai {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    
    &--user {
        background: #e5e7eb;
        color: #6b7280;
    }
    
    @media (max-width: 768px) {
        width: 32px;
        height: 32px;
    }
}

.message__body {
    flex: 1;
    min-width: 0;
}

.message__role {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 8px;
}

.message__content {
    font-size: 15px;
    line-height: 1.7;
    color: #1f2937;
}

.plain-text {
    white-space: pre-wrap;
    word-break: break-word;
}

.loading-cursor {
    display: inline-block;
    width: 8px;
    height: 18px;
    background: #667eea;
    margin-left: 4px;
    vertical-align: text-bottom;
    border-radius: 2px;
    animation: blink 1s ease-in-out infinite;
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0.3; }
}

.message__sources {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
}

.source-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 12px;
    color: #4b5563;
    transition: all 0.2s;
    
    &:hover {
        background: #e5e7eb;
    }
    
    &--tool {
        background: #eff6ff;
        border-color: #bfdbfe;
        color: #2563eb;
        
        &:hover {
            background: #dbeafe;
        }
    }
    
    .page-num {
        color: #9ca3af;
        margin-left: 4px;
    }
}

.message__meta {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 12px;
    font-size: 12px;
    color: #9ca3af;
}

.meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
}

/* Markdown Styles */
.markdown-body {
    color: #1f2937;
    
    :deep(p) {
        margin: 0 0 16px 0;
        &:last-child { margin-bottom: 0; }
    }
    
    :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
        margin: 24px 0 12px 0;
        font-weight: 600;
        color: #111827;
        line-height: 1.4;
        
        &:first-child { margin-top: 0; }
    }
    
    :deep(h1) { font-size: 1.5em; }
    :deep(h2) { font-size: 1.3em; }
    :deep(h3) { font-size: 1.15em; }
    
    :deep(pre) {
        background: #1e1e2e;
        border-radius: 8px;
        padding: 16px;
        overflow-x: auto;
        margin: 16px 0;
        
        code {
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.6;
            color: #cdd6f4;
            background: transparent;
            padding: 0;
        }
    }
    
    :deep(code) {
        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        background: #f3f4f6;
        color: #dc2626;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
    }
    
    :deep(ul), :deep(ol) {
        margin: 12px 0;
        padding-left: 24px;
    }
    
    :deep(li) {
        margin: 6px 0;
    }
    
    :deep(strong) {
        font-weight: 600;
        color: #111827;
    }
    
    :deep(a) {
        color: #2563eb;
        text-decoration: none;
        &:hover { text-decoration: underline; }
    }
    
    :deep(blockquote) {
        border-left: 4px solid #e5e7eb;
        margin: 16px 0;
        padding-left: 16px;
        color: #6b7280;
        font-style: italic;
    }
    
    :deep(table) {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;
        font-size: 14px;
    }
    
    :deep(th), :deep(td) {
        padding: 10px 14px;
        border: 1px solid #e5e7eb;
        text-align: left;
    }
    
    :deep(th) {
        background: #f9fafb;
        font-weight: 600;
    }
    
    :deep(hr) {
        border: none;
        border-top: 1px solid #e5e7eb;
        margin: 24px 0;
    }
}
</style>
