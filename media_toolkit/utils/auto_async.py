import asyncio
import inspect


def auto_async(func_async, func_sync):
    def wrapper(*args, **kwargs):
        if inspect.iscoroutinefunction(func_async) and asyncio.get_event_loop().is_running():
            return func_async(*args, **kwargs)
        return func_sync(*args, **kwargs)
    return wrapper
