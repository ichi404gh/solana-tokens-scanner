import asyncio

import log

logger = log.logger.getChild(__name__)

PING_INTERVAL=3.0

async def keep_alive(ws):
    while True:
        try:
            await asyncio.sleep(PING_INTERVAL)
            await ws.ping()
        except Exception as e:
            logger.error(f"Error sending ping: {e}")
            break
