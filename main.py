import asyncio
from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from pkg.core.bootutils import lifecycle
from typing import Union

# 注册插件
@register(name="定时热重载", description="定时执行热重载", version="0.1", author="孤寂")
class AutoReloaderPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        # 默认配置
        self.reload_interval = 1200  # 默认20分钟（1200秒）
        self.reload_scopes = [
            lifecycle.LifecycleControlScope.PLATFORM.value,  # 默认只重载平台
            # lifecycle.LifecycleControlScope.PLUGIN.value,
        ]
        self.is_auto_reload = True  # 默认开启自动重载
        self.task = None
        self.admin_users = ["admin_user_id"]  # 允许操作的管理员用户ID列表

    async def initialize(self):
        """初始化时启动定时任务"""
        if self.is_auto_reload:
            self.task = asyncio.create_task(self.schedule_reload())

    async def unload(self):
        """插件卸载时停止任务"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def schedule_reload(self):
        """定时重载任务"""
        while True:
            try:
                await asyncio.sleep(self.reload_interval)
                await self.do_reload()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.ap.logger.error(f"定时重载失败: {str(e)}")

    async def do_reload(self, scope: Union[str, list] = None):
        """执行重载操作"""
        try:
            scopes = scope or self.reload_scopes
            for s in scopes:
                self.ap.logger.info(f"开始热重载: scope={s}")
                await lifecycle.reload(s)
                self.ap.logger.info(f"热重载完成: scope={s}")
            return True
        except Exception as e:
            self.ap.logger.error(f"热重载失败: {str(e)}")
            return False

    @handler(PersonNormalMessageReceived)
    async def handle_person_message(self, ctx: EventContext):
        await self.process_command(ctx, is_group=False)

    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        await self.process_command(ctx, is_group=True)

    async def process_command(self, ctx: EventContext, is_group: bool):
        """处理控制命令"""
        msg = ctx.event.text_message.strip()
        sender = ctx.event.sender_id

        # 权限检查
        if sender not in self.admin_users:
            return

        # 解析命令
        if msg.startswith("/reload"):
            parts = msg.split()
            if len(parts) == 1:
                # 立即执行重载
                success = await self.do_reload()
                reply = "✅ 热重载完成" if success else "❌ 热重载失败"
            elif len(parts) >= 2:
                # 带参数的重载
                scope_map = {
                    "platform": [lifecycle.LifecycleControlScope.PLATFORM.value],
                    "plugin": [lifecycle.LifecycleControlScope.PLUGIN.value],
                    "all": [
                        lifecycle.LifecycleControlScope.PLATFORM.value,
                        lifecycle.LifecycleControlScope.PLUGIN.value
                    ]
                }
                scope = scope_map.get(parts[1].lower())
                if scope:
                    success = await self.do_reload(scope)
                    reply = f"✅ {parts[1]}重载完成" if success else f"❌ {parts[1]}重载失败"
                else:
                    reply = "❌ 无效的重载范围，可用值：platform/plugin/all"
            ctx.add_return("reply", [reply])
            ctx.prevent_default()

        elif msg.startswith("/reload_interval"):
            parts = msg.split()
            if len(parts) == 2 and parts[1].isdigit():
                new_interval = int(parts[1])
                if new_interval >= 60:  # 最小60秒
                    self.reload_interval = new_interval
                    reply = f"✅ 重载间隔已设置为 {new_interval} 秒"
                else:
                    reply = "❌ 间隔时间不能小于60秒"
            else:
                reply = "❌ 用法：/reload_interval <秒数>"
            ctx.add_return("reply", [reply])
            ctx.prevent_default()

        elif msg == "/auto_reload on":
            if not self.is_auto_reload:
                self.is_auto_reload = True
                self.task = asyncio.create_task(self.schedule_reload())
                reply = "✅ 已开启自动重载"
            ctx.add_return("reply", [reply])
            ctx.prevent_default()

        elif msg == "/auto_reload off":
            if self.is_auto_reload:
                self.is_auto_reload = False
                if self.task:
                    self.task.cancel()
                reply = "✅ 已关闭自动重载"
            ctx.add_return("reply", [reply])
            ctx.prevent_default()

    def __del__(self):
        if self.task:
            self.task.cancel()
