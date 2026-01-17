#!/usr/bin/env python
"""
Django 项目管理脚本 (Command-line Utility)
用于执行各种管理命令，如启动服务器、数据库迁移等。
"""
import os
import sys


def main():
    """主函数：运行管理任务"""
    # 默认使用 'config.settings' 作为配置文件
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "无法导入 Django。请确认：\n"
            "1. 您是否已安装 Django (pip install django)？\n"
            "2. 您是否激活了虚拟环境 (Virtual Environment)？"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
