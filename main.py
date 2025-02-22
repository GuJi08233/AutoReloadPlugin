from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import asyncio
from pkg.core import core_entities

@register(name="AutoReload", 
         description="定时执行热重载保持连接", 
         version="1.0", 
         author="YourName")
class AutoReloadPlugin(BasePlugin):
    
    def __init__(self, host: APIHost):
        self.host = host
        self.reload_interval = 1200  # 20分钟
        self.reload_scopes = [
            core_entities.LifecycleControlScope.PLATFORM.value
        ]
        self._task = None

    async def initialize(self):
        """异步初始化启动定时任务"""
        self._task = asyncio.create_task(self.schedule_reload())
        
    async def schedule_reload(self):
        """定时重载任务"""
        while True:
            try:
                for scope in self.reload_scopes:
                    self.host.logger.info(f"执行定时热重载: scope={scope}")
                    # 调用主程序的重载接口
                    await self.host.invoke_method(
                        "lifecycle_control",
                        "reload",
                        scope=scope
                    )
                await asyncio.sleep(self.reload_interval)
            except Exception as e:
                self.host.logger.error(f"热重载任务异常: {str(e)}")

    async def unload(self):
        """插件卸载时取消任务"""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def __del__(self):
        pass
