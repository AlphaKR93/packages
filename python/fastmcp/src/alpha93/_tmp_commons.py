def catch(*types: type):
    async def func(fn, /):
        try: return await fn(), None
        except types as e: return None, e
    return func
