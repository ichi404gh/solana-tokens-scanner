import asyncio
import os
import logging
from dataclasses import dataclass

import aiohttp
from solders.solders import Pubkey

MAX_ATTEMPTS = 3
RETRY_DELAY = 5  # secs

WELL_KNOWN_TOKENS = [
    Pubkey.from_string('So11111111111111111111111111111111111111111'),  # SOL
    Pubkey.from_string('So11111111111111111111111111111111111111112'),  # WSOL
    Pubkey.from_string('BaZGLMCT6yiwiNzqfxwZNvjWaacFcgXw7qhR45KRAja5'),  # Raydium Concentrated Liquidity
]

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@dataclass
class MetadataJob:
    token: Pubkey
    attempts: int = 0


class MetadataProcessor:
    def __init__(self):
        self.queue = asyncio.Queue()

    def run(self):
        asyncio.create_task(self.process_metadata())

    async def enqueue_metadata_job(self,  tokens):
        for token in tokens:
            if token in WELL_KNOWN_TOKENS:
                continue
            logger.debug(f"enqueuing {token}")
            job = MetadataJob(token=token)
            await self.queue.put(job)
            logger.debug(f"enqueued job")


    async def requeue_later(self, item: MetadataJob):
        logger.debug('requeueing')
        await asyncio.sleep(RETRY_DELAY)
        await self.queue.put(item)
        logger.debug('done requeueing')


    async def get_token_metadata(self, mint):
        url = "https://mainnet.helius-rpc.com/"

        querystring = {"api-key": os.environ.get('HELIUS_API_KEY')}

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getAsset",
            "params": {
                "id": mint,
                "options": {"showInscription": False}
            }
        }
        headers = {"Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json=payload, headers=headers, params=querystring)
            data = await resp.json()
            return data['result']['content']['metadata']


    async def process_metadata(self):
        while True:
            job: MetadataJob = await self.queue.get()
            logger.debug(f"processing {job.token}")
            try:

                metadata = await self.get_token_metadata(str(job.token))
                logger.debug("metadata:")
                logger.debug(metadata)
            except Exception as e:
                job.attempts += 1
                if job.attempts <= MAX_ATTEMPTS:
                    logger.warning(f"Ошибка при обработке {job.token}, повтор {job.attempts}")
                    asyncio.create_task(self.requeue_later(job))
                else:
                    logger.warning(f"Отказ от {job.token} после {MAX_ATTEMPTS} попыток: {e}")
            finally:
                self.queue.task_done()
