<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Sparkles, User, Mail, Lock, ArrowRight, Loader2 } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const isLoginMode = ref(true)
const username = ref('')
const password = ref('')
const email = ref('')
const error = ref('')
const loading = ref(false)

const toggleMode = () => {
    isLoginMode.value = !isLoginMode.value
    error.value = ''
}

const handleSubmit = async () => {
    if (!username.value || !password.value) {
        error.value = '请填写用户名和密码'
        return
    }

    loading.value = true
    error.value = ''

    try {
        if (isLoginMode.value) {
            await authStore.login(username.value, password.value)
        } else {
            await authStore.register(username.value, password.value, email.value || undefined)
        }
        router.push('/')
    } catch (e: any) {
        error.value = e.message
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <div class="auth-page">
        <div class="auth-container">
            <!-- Left Panel - Branding -->
            <div class="branding-panel">
                <div class="branding-content">
                    <div class="logo">
                        <Sparkles :size="40" />
                    </div>
                    <h1>AI Chat</h1>
                    <p>智能对话助手，为您提供高效、准确的 AI 交互体验</p>

                    <div class="features">
                        <div class="feature">
                            <div class="feature-icon">💬</div>
                            <div class="feature-text">
                                <strong>智能对话</strong>
                                <span>自然语言理解与生成</span>
                            </div>
                        </div>
                        <div class="feature">
                            <div class="feature-icon">📚</div>
                            <div class="feature-text">
                                <strong>知识检索</strong>
                                <span>基于文档的 RAG 问答</span>
                            </div>
                        </div>
                        <div class="feature">
                            <div class="feature-icon">🔧</div>
                            <div class="feature-text">
                                <strong>工具调用</strong>
                                <span>MCP 协议工具集成</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Panel - Form -->
            <div class="form-panel">
                <div class="form-container">
                    <div class="form-header">
                        <h2>{{ isLoginMode ? '欢迎回来' : '创建账户' }}</h2>
                        <p>{{ isLoginMode ? '登录您的账户以继续' : '注册一个新账户开始使用' }}</p>
                    </div>

                    <form @submit.prevent="handleSubmit">
                        <!-- Username -->
                        <div class="form-group">
                            <label>
                                <User :size="16" />
                                用户名
                            </label>
                            <input v-model="username" type="text" placeholder="请输入用户名" :disabled="loading"
                                autocomplete="username" />
                        </div>

                        <!-- Email (Register Only) -->
                        <div v-if="!isLoginMode" class="form-group">
                            <label>
                                <Mail :size="16" />
                                邮箱 <span class="optional">(可选)</span>
                            </label>
                            <input v-model="email" type="email" placeholder="请输入邮箱" :disabled="loading" />
                        </div>

                        <!-- Password -->
                        <div class="form-group">
                            <label>
                                <Lock :size="16" />
                                密码
                            </label>
                            <input v-model="password" type="password" placeholder="请输入密码" :disabled="loading"
                                autocomplete="current-password" />
                        </div>

                        <!-- Error Message -->
                        <Transition name="shake">
                            <div v-if="error" class="error-message">
                                {{ error }}
                            </div>
                        </Transition>

                        <!-- Submit Button -->
                        <button type="submit" class="submit-btn" :disabled="loading">
                            <Loader2 v-if="loading" :size="20" class="spinner" />
                            <template v-else>
                                <span>{{ isLoginMode ? '登录' : '注册' }}</span>
                                <ArrowRight :size="18" />
                            </template>
                        </button>
                    </form>

                    <!-- Toggle Mode -->
                    <div class="toggle-section">
                        <span>{{ isLoginMode ? '还没有账户？' : '已有账户？' }}</span>
                        <button @click="toggleMode" type="button">
                            {{ isLoginMode ? '立即注册' : '立即登录' }}
                        </button>
                    </div>
                </div>

                <p class="footer">© 2026 AI Chat · 安全登录</p>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
$primary: #10a37f;
$primary-hover: #0d8c6d;
$bg-dark: #202123;
$bg-darker: #171717;
$bg-light: #343541;
$text-primary: #ececf1;
$text-secondary: #8e8ea0;
$border-color: #4e4f60;

.auth-page {
    min-height: 100vh;
    display: flex;
    background: $bg-darker;
}

.auth-container {
    display: flex;
    width: 100%;

    @media (max-width: 900px) {
        flex-direction: column;
    }
}

// Branding Panel
.branding-panel {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, $bg-dark 0%, $bg-light 100%);
    padding: 40px;
    position: relative;
    overflow: hidden;

    &::before {
        content: '';
        position: absolute;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba($primary, 0.15) 0%, transparent 70%);
        top: -100px;
        right: -100px;
        border-radius: 50%;
    }

    &::after {
        content: '';
        position: absolute;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(#5436da, 0.1) 0%, transparent 70%);
        bottom: -50px;
        left: -50px;
        border-radius: 50%;
    }

    @media (max-width: 900px) {
        display: none;
    }
}

.branding-content {
    max-width: 400px;
    position: relative;
    z-index: 1;
}

.logo {
    width: 72px;
    height: 72px;
    background: $primary;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 20px 40px rgba($primary, 0.3);
}

.branding-content h1 {
    font-size: 36px;
    font-weight: 700;
    color: $text-primary;
    margin: 0 0 12px;
}

.branding-content>p {
    font-size: 16px;
    color: $text-secondary;
    line-height: 1.6;
    margin: 0 0 40px;
}

.features {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.feature {
    display: flex;
    align-items: flex-start;
    gap: 16px;
}

.feature-icon {
    width: 44px;
    height: 44px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid $border-color;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

.feature-text {
    display: flex;
    flex-direction: column;
    gap: 2px;

    strong {
        font-size: 15px;
        font-weight: 600;
        color: $text-primary;
    }

    span {
        font-size: 13px;
        color: $text-secondary;
    }
}

// Form Panel
.form-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px;
    background: $bg-dark;

    @media (max-width: 900px) {
        min-height: 100vh;
    }
}

.form-container {
    width: 100%;
    max-width: 380px;
}

.form-header {
    text-align: center;
    margin-bottom: 32px;

    h2 {
        font-size: 28px;
        font-weight: 700;
        color: $text-primary;
        margin: 0 0 8px;
    }

    p {
        font-size: 14px;
        color: $text-secondary;
        margin: 0;
    }
}

form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;

    label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        font-weight: 500;
        color: $text-primary;

        .optional {
            font-weight: 400;
            color: $text-secondary;
            font-size: 12px;
        }
    }

    input {
        width: 100%;
        padding: 14px 16px;
        background: $bg-light;
        border: 1px solid $border-color;
        border-radius: 10px;
        font-size: 15px;
        color: $text-primary;
        transition: all 0.2s;
        box-sizing: border-box;

        &::placeholder {
            color: $text-secondary;
        }

        &:focus {
            outline: none;
            border-color: $primary;
            box-shadow: 0 0 0 3px rgba($primary, 0.15);
        }

        &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
    }
}

.error-message {
    background: rgba(#ef4444, 0.1);
    border: 1px solid rgba(#ef4444, 0.3);
    color: #f87171;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 14px;
}

.submit-btn {
    width: 100%;
    padding: 14px;
    background: $primary;
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s;
    margin-top: 8px;

    &:hover:not(:disabled) {
        background: $primary-hover;
    }

    &:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
}

.spinner {
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.toggle-section {
    text-align: center;
    margin-top: 28px;
    padding-top: 28px;
    border-top: 1px solid $border-color;

    span {
        color: $text-secondary;
        font-size: 14px;
    }

    button {
        background: none;
        border: none;
        color: $primary;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        margin-left: 4px;
        transition: all 0.15s;

        &:hover {
            text-decoration: underline;
        }
    }
}

.footer {
    text-align: center;
    color: $text-secondary;
    font-size: 12px;
    margin-top: 40px;
}

// Animations
.shake-enter-active {
    animation: shake 0.4s ease;
}

@keyframes shake {

    0%,
    100% {
        transform: translateX(0);
    }

    20%,
    60% {
        transform: translateX(-8px);
    }

    40%,
    80% {
        transform: translateX(8px);
    }
}
</style>
