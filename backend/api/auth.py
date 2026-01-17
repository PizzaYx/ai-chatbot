"""
用户认证 API
使用 PyJWT 实现 JWT 认证

提供:
- POST /api/auth/register - 用户注册
- POST /api/auth/login - 用户登录 (返回 JWT Token)
- GET /api/auth/me - 获取当前用户信息 (需要 Token)
"""
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional

from ninja import Router, Schema
from ninja.security import HttpBearer
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password

router = Router(tags=["Auth"])

# JWT 配置
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # Token 有效期 7 天


# ============ Schemas ============

class RegisterSchema(Schema):
    username: str
    password: str
    email: Optional[str] = None

class LoginSchema(Schema):
    username: str
    password: str

class TokenSchema(Schema):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserSchema(Schema):
    id: int
    username: str
    email: Optional[str]
    is_staff: bool

class ErrorSchema(Schema):
    detail: str


# ============ JWT Utils ============

def create_token(user_id: int) -> str:
    """生成 JWT Token"""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token 过期
    except jwt.InvalidTokenError:
        return None  # Token 无效


# ============ Auth Bearer ============

class JWTAuth(HttpBearer):
    """
    JWT 认证类
    用于保护需要登录的 API 接口
    使用方式: @router.get("/protected", auth=JWTAuth())
    """
    def authenticate(self, request, token: str) -> Optional[User]:
        payload = decode_token(token)
        if payload is None:
            return None
        
        user_id = payload.get("user_id")
        try:
            user = User.objects.get(id=user_id)
            return user
        except User.DoesNotExist:
            return None


# ============ API Endpoints ============

@router.post("/register", response={200: TokenSchema, 400: ErrorSchema})
def register(request, payload: RegisterSchema):
    """用户注册"""
    # 检查用户名是否已存在
    if User.objects.filter(username=payload.username).exists():
        return 400, {"detail": "用户名已存在"}
    
    # 检查邮箱是否已存在
    if payload.email and User.objects.filter(email=payload.email).exists():
        return 400, {"detail": "邮箱已被注册"}
    
    # 创建用户
    user = User.objects.create(
        username=payload.username,
        email=payload.email or "",
        password=make_password(payload.password),
    )
    
    # 生成 Token
    token = create_token(user.id)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
        }
    }


@router.post("/login", response={200: TokenSchema, 401: ErrorSchema})
def login(request, payload: LoginSchema):
    """用户登录"""
    try:
        user = User.objects.get(username=payload.username)
    except User.DoesNotExist:
        return 401, {"detail": "用户名或密码错误"}
    
    # 验证密码
    if not check_password(payload.password, user.password):
        return 401, {"detail": "用户名或密码错误"}
    
    # 生成 Token
    token = create_token(user.id)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
        }
    }


@router.get("/me", response={200: UserSchema, 401: ErrorSchema}, auth=JWTAuth())
def get_current_user(request):
    """获取当前登录用户信息"""
    user = request.auth
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
    }
