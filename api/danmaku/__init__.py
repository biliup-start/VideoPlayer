from datetime import datetime
import logging
import re, asyncio, aiohttp

# from .youtube import Youtube
from DMR.utils import *

__all__ = ["DanmakuClient"]

# 使用DMC的API，只实现了几个类方法
class site_class:
    @staticmethod
    def get(platform):
        if platform == 'bilibili':
            from .bilibili import Bilibili
            return Bilibili
        elif platform == 'douyu':
            from .douyu import Douyu
            return Douyu
        elif platform == 'huya':
            from .huya import Huya
            return Huya
        elif platform == 'cc':
            from .cc import CC
            return CC
        elif platform == 'twitch':
            from .twitch import Twitch
            return Twitch
        elif platform == 'douyin':
            from .douyin import Douyin
            return Douyin
        elif platform == 'youtube':
            from .youtube import Youtube
            return Youtube
        else:
            raise NotImplementedError(f'Platform {platform} is not supported.')

# 使用自建API，DMC会实例化这个类然后调用start方法启动
site_class_v2 = {
}

class DanmakuClient:
    def __init__(self, url, q: asyncio.Queue, **kwargs):
        self.__url = ""
        self.__site_api = None
        self.__site_class = None
        self.__hs = None
        self.__ws = None
        self.__stop = False
        self._dm_queue = q
        self.__kwargs = kwargs
        if "http://" == url[:7] or "https://" == url[:8]:
            self.__url = url
        else:
            self.__url = "http://" + url
        self.plat, self.rid = split_url(url)
        if site_class.get(self.plat):
            self.__hs = aiohttp.ClientSession()
            self.__site_api = site_class.get(self.plat)
        elif site_class_v2.get(self.plat):
            self.__site_class = site_class_v2.get(self.plat)
        else:
            raise Exception(f'Error URL {url}')

    async def init_ws(self):
        ws_url, reg_datas = await self.__site_api.get_ws_info(self.__url, **self.__kwargs)
        self.__ws = await self.__hs.ws_connect(ws_url, headers=getattr(self.__site_api, 'headers', {}))
        for reg_data in reg_datas:
            if type(reg_data) == str:
                await self.__ws.send_str(reg_data)
            else:
                await self.__ws.send_bytes(reg_data)

    async def heartbeats(self):
        while self.__stop != True:
            # print('heartbeat')
            await asyncio.sleep(20)
            try:
                if type(self.__site_api.heartbeat) == str:
                    await self.__ws.send_str(self.__site_api.heartbeat)
                else:
                    await self.__ws.send_bytes(self.__site_api.heartbeat)
            except:
                pass

    async def fetch_danmaku(self):
        while self.__stop != True:
            msg = await self.__ws.receive()
            if msg.type in [aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR]:
                raise RuntimeError('Websocket Closed')
            
            result = self.__site_api.decode_msg(msg.data)
            if isinstance(result, tuple):
                ms, ack = result
                if ack is not None:
                    # 发送ack包
                    if type(ack) == str:
                        await self.__ws.send_str(ack)
                    else:
                        await self.__ws.send_bytes(ack)
            else:
                ms = result

            for m in ms:
                await self._dm_queue.put(m)

    async def start(self):
        if self.__site_api != None:
            await self.init_ws()
            await asyncio.gather(
                self.heartbeats(),
                self.fetch_danmaku(),
            )
        else:
            self.__site_class = self.__site_class(rid=self.rid, q=self._dm_queue)
            await self.__site_class.start()

    async def stop(self):
        self.__stop = True
        if self.__site_api != None:
            await self.__hs.close()
        else:
            await self.__site_class.stop()
