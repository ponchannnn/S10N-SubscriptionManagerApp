"""共通の同期APIと担当画面のasyncイベントを接続する．"""
import asyncio
import inspect


async def call_api(api, method, *args):
    function = getattr(api, method)
    if inspect.iscoroutinefunction(function):
        return await function(*args)
    return await asyncio.to_thread(function, *args)
