from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import PersonNormalMessageReceived, GroupNormalMessageReceived
from pkg.core.bootutils import lifecycle
import asyncio
import re
from typing import List, Union

@register(name="sdad", description="说的都是", version="0.1", author="小多少点")
class AutoReloaderPlugin(BasePlugin):
    def __init__(self, host: APIHost):
        super().__init__(host)  # 必须调用父类初始化
        # 配置项
        self.default_interval = 1200  # 默认20分钟
        self.min_interval = 300  # 最小5分钟
        self.reload_scopes = [
            lifecycle.LifecycleControlScope.PLATFORM.value,
            lifecycle.LifecycleControlScope.PLUGIN.value
        ]
        self.admin_users = ["your_admin_id_here"]  # 必须配置管理员ID
        self.task = None

    async def initialize(self):
        """异步初始化"""
        self.ap.logger.info("AutoReloader 插件已加载")
        if self.default_interval >= self.min_interval:
            self.task = asyncio.create_task(self.schedule_reload())

    async def unload(self):
        """插件卸载处理"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.ap.logger.info("AutoReloader 插件已卸载")

    async def schedule_reload(self):
        """定时任务循环"""
        while True:
            try:
                await asyncio.sleep(self.default_interval)
                await self.execute_reload()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.ap.logger.error(f"定时任务异常: {str(e)}")

    async def execute_reload(self, scopes: List[str] = None):
        """执行重载操作"""
        try:
            targets = scopes or self.reload_scopes
            for scope in targets:
                self.ap.logger.info(f"开始重载: {scope}")
                await lifecycle.reload(scope)
                self.ap.logger.info(f"重载完成: {scope}")
            return True
        except Exception as e:
            self.ap.logger.error(f"重载失败: {str(e)}")
            return False

    @handler(PersonNormalMessageReceived)
    @handler(GroupNormalMessageReceived)
    async def handle_message(self, ctx: EventContext):
        """统一消息处理"""
        # 权限验证
        if ctx.event.sender_id not in self.admin_users:
            return

        # 命令解析
        msg = re.sub(r'@\S+\s*', '', ctx.event.text_message).strip()
        
        if msg.startswith("/reload"):
            await self.handle_reload_command(ctx, msg)
        elif msg.startswith("/reload_interval"):
            await self.handle_interval_command(ctx, msg)

    async def handle_reload_command(self, ctx: EventContext, command: str):
        """处理重载命令"""
        parts = command.split()
        scope_map = {
            "platform": [lifecycle.LifecycleControlScope.PLATFORM.value],
            "plugins": [lifecycle.LifecycleControlScope.PLUGIN.value],
            "all": self.reload_scopes
        }
        
        target = parts[1].lower() if len(parts) > 1 else "all"
        scopes = scope_map.get(target, self.reload_scopes)
        
        success = await self.execute_reload(scopes)
        reply = f"✅ {target}重载成功" if success else f"❌ {target}重载失败"
        ctx.add_return("reply", [reply])
        ctx.prevent_default()

    async def handle_interval_command(self, ctx: EventContext, command: str):
        """处理间隔设置命令"""
        parts = command.split()
        if len(parts) != 2 or not parts[1].isdigit():
            ctx.add_return("reply", ["❌ 格式错误，使用 /reload_interval <秒数>"])
            ctx.prevent_default()
            return

        new_interval = int(parts[1])
        if new_interval < self.min_interval:
            ctx.add_return("reply", [f"❌ 间隔不能小于{self.min_interval}秒"])
            ctx.prevent_default()
            return

        self.default_interval = new_interval
        # 重启定时任务
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(self.schedule_reload())
        
        ctx.add_return("reply", [f"✅ 重载间隔已设置为{new_interval}秒"])
        ctx.prevent_default()
