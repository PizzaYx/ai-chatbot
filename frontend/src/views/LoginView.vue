<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
    <div class="login-page">
        <div class="login-container">
            <!-- Logo & Title -->
            <div class="header">
                <div class="logo">🤖</div>
                <h1>AI 知识助手</h1>
                <p>{{ isLoginMode ? '登录您的账户' : '创建新账户' }}</p>
            </div>

            <!-- Form Card -->
            <div class="form-card">
                <form @submit.prevent="handleSubmit">
                    <!-- Username -->
                    <div class="form-group">
                        <label>用户名</label>
                        <input v-model="username" type="text" placeholder="请输入用户名" :disabled="loading" />
                    </div>

                    <!-- Email (Register Only) -->
                    <div v-if="!isLoginMode" class="form-group">
                        <label>邮箱 (可选)</label>
                        <input v-model="email" type="email" placeholder="请输入邮箱" :disabled="loading" />
                    </div>

                    <!-- Password -->
                    <div class="form-group">
                        <label>密码</label>
                        <input v-model="password" type="password" placeholder="请输入密码" :disabled="loading" />
                    </div>

                    <!-- Error -->
                    <div v-if="error" class="error-message">
                        {{ error }}
                    </div>

                    <!-- Submit Button -->
                    <button type="submit" class="submit-btn" :disabled="loading">
                        <span v-if="loading" class="loading-spinner"></span>
                        <span v-else>{{ isLoginMode ? '登录' : '注册' }}</span>
                    </button>
                </form>

                <!-- Toggle Mode -->
                <div class="toggle-mode">
                    <p>
                        {{ isLoginMode ? '还没有账户？' : '已有账户？' }}
                        <button @click="toggleMode" type="button">
                            {{ isLoginMode ? '立即注册' : '立即登录' }}
                        </button>
                    </p>
                </div>
            </div>

            <!-- Footer -->
            <p class="footer">© 2026 AI Knowledge Assistant</p>
        </div>
    </div>
</template>

<style scoped lang="scss">
.login-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    padding: 20px;
}

.login-container {
    width: 100%;
    max-width: 400px;
}

.header {
    text-align: center;
    margin-bottom: 30px;

    .logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 64px;
        height: 64px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        font-size: 32px;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        margin-bottom: 16px;
    }

    h1 {
        font-size: 24px;
        font-weight: 700;
        color: #333;
        margin: 0 0 8px 0;
    }

    p {
        color: #666;
        margin: 0;
    }
}

.form-card {
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(10px);
    border-radius: 20px;
    padding: 32px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);

    form {
        display: flex;
        flex-direction: column;
        gap: 20px;
    }
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;

    label {
        font-size: 14px;
        font-weight: 500;
        color: #333;
    }

    input {
        width: 100%;
        padding: 14px 16px;
        background: #f5f7fa;
        border: 1px solid #e1e5eb;
        border-radius: 12px;
        font-size: 16px;
        transition: all 0.3s ease;
        box-sizing: border-box;

        &:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }

        &:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
    }
}

.error-message {
    background: #fff0f0;
    color: #e53935;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 14px;
}

.submit-btn {
    width: 100%;
    padding: 14px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;

    &:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
    }

    &:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
}

.loading-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.toggle-mode {
    margin-top: 24px;
    text-align: center;

    p {
        color: #666;
        margin: 0;
    }

    button {
        background: none;
        border: none;
        color: #667eea;
        font-weight: 600;
        cursor: pointer;
        margin-left: 4px;

        &:hover {
            text-decoration: underline;
        }
    }
}

.footer {
    text-align: center;
    color: #999;
    font-size: 12px;
    margin-top: 30px;
}
</style>
