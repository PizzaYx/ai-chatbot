import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
    // 从 localStorage 读取或使用系统偏好
    const getInitialTheme = (): Theme => {
        const stored = localStorage.getItem('theme') as Theme | null
        if (stored) return stored
        
        // 检查系统偏好
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            return 'light'
        }
        return 'dark'
    }

    const theme = ref<Theme>(getInitialTheme())

    const toggleTheme = () => {
        theme.value = theme.value === 'dark' ? 'light' : 'dark'
    }

    const setTheme = (newTheme: Theme) => {
        theme.value = newTheme
    }

    // 监听变化并持久化
    watch(theme, (newTheme) => {
        localStorage.setItem('theme', newTheme)
        document.documentElement.setAttribute('data-theme', newTheme)
    }, { immediate: true })

    return {
        theme,
        toggleTheme,
        setTheme
    }
})
