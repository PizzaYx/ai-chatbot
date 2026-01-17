import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
    history: createWebHashHistory(),
    routes: [
        {
            path: '/',
            name: 'chat',
            component: () => import('@/views/ChatView.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/login',
            name: 'login',
            component: () => import('@/views/LoginView.vue'),
            meta: { guest: true }
        },
    ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
    const authStore = useAuthStore()
    
    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        // 需要登录但未登录，跳转到登录页
        next({ name: 'login' })
    } else if (to.meta.guest && authStore.isAuthenticated) {
        // 已登录用户访问登录页，跳转到首页
        next({ name: 'chat' })
    } else {
        next()
    }
})

export default router
