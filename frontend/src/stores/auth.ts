import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface User {
    id: number
    username: string
    email: string
    is_staff: boolean
}

export const useAuthStore = defineStore('auth', () => {
    // State
    const token = ref<string | null>(localStorage.getItem('auth_token'))
    const user = ref<User | null>(null)

    // 尝试从 localStorage 恢复用户信息
    const savedUser = localStorage.getItem('auth_user')
    if (savedUser) {
        try {
            user.value = JSON.parse(savedUser)
        } catch (e) {
            localStorage.removeItem('auth_user')
        }
    }

    // Getters
    const isAuthenticated = computed(() => !!token.value)

    // Actions
    async function login(username: string, password: string) {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        })

        if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || '登录失败')
        }

        const data = await response.json()
        setAuth(data.access_token, data.user)
        return data.user
    }

    async function register(username: string, password: string, email?: string) {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, email })
        })

        if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || '注册失败')
        }

        const data = await response.json()
        setAuth(data.access_token, data.user)
        return data.user
    }

    function setAuth(newToken: string, newUser: User) {
        token.value = newToken
        user.value = newUser
        localStorage.setItem('auth_token', newToken)
        localStorage.setItem('auth_user', JSON.stringify(newUser))
    }

    function logout() {
        token.value = null
        user.value = null
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
        localStorage.removeItem('chat_session_id') // 同时清除聊天 session
    }

    // 获取带 Token 的 fetch headers
    function getAuthHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json'
        }
        if (token.value) {
            headers['Authorization'] = `Bearer ${token.value}`
        }
        return headers
    }

    return {
        token,
        user,
        isAuthenticated,
        login,
        register,
        logout,
        getAuthHeaders,
    }
})
