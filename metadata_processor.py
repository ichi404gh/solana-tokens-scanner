import asyncio
import os
from dataclasses import dataclass
from typing import Iterable

import aiohttp
from solders.solders import Pubkey

import log

logger = log.logger.getChild(__name__)

MAX_ATTEMPTS = 4
RETRY_DELAY = 2  # secs

WELL_KNOWN_TOKENS = [
    Pubkey.from_string('So11111111111111111111111111111111111111111'),  # SOL
    Pubkey.from_string('So11111111111111111111111111111111111111112'),  # WSOL
    Pubkey.from_string('Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'),  # USDT
    Pubkey.from_string('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),  # USDC
]


@dataclass
class MetadataJob:
    tokens: (Pubkey, Pubkey)


def _pubkeys_to_str(pks: Iterable[Pubkey]) -> str:
    return ", ".join(map(lambda pk: str(pk), pks))


class MetadataProcessor:
    def __init__(self, job_queue: asyncio.Queue, shutdown_event: asyncio.Event):
        self.job_queue = job_queue
        self.shutdown_event = shutdown_event
        self.patterns = set(map(lambda s: s.lower(), os.getenv('SEARCH_PATTERN').split(',')))

    def run(self):
        asyncio.create_task(self.worker())

    async def requeue_later(self, item: MetadataJob):
        logger.debug('requeueing')
        await asyncio.sleep(RETRY_DELAY)
        await self.job_queue.put(item)
        logger.debug('done requeueing')

    async def get_token_metadata(self, mint):
        url = "https://mainnet.helius-rpc.com/"

        api_key = os.environ.get('HELIUS_API_KEY')
        if not api_key:
            raise ValueError("HELIUS_API_KEY not set in environment variables")

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getAsset",
            "params": {
                "id": mint,
                "options": {"showInscription": False}
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    params={"api-key": api_key}) as resp:
                if resp.status != 200:
                    raise aiohttp.ClientError(f"HTTP {resp.status}: {await resp.text()}")

                data = await resp.json()
                if 'error' in data:
                    raise ValueError(f"API error: {data['error']}")
                return data['result']['content']['metadata']

    async def process_token(self, token: Pubkey):
        if token in WELL_KNOWN_TOKENS:
            logger.debug(f"Skipping well-known token: {str(token)}")
            return None

        for attempt in range(MAX_ATTEMPTS):
            try:
                metadata = await self.get_token_metadata(str(token))
                return metadata
            except Exception as e:
                logger.error(f"Error processing {str(token)}: {e}")
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                logger.error(f"Giving up on {str(token)}")
                return None

        return None

    async def worker(self):
        logger.debug("Starting metadata extraction worker")
        while not self.shutdown_event.is_set():
            try:
                job: MetadataJob = await self.job_queue.get()
                logger.debug(f"processing {_pubkeys_to_str(job.tokens)}")

                results = await asyncio.gather(
                    self.process_token(job.tokens[0]),
                    self.process_token(job.tokens[1]),
                )

                await self.report(job.tokens, results)
            except Exception as e:
                logger.error(f"Unexpected error occurred: {e}")
            finally:
                self.job_queue.task_done()

    async def report(self, tokens: Iterable[Pubkey], metadata):
        tks = [f"{str(t)[:4]}...{str(t)[-4:]}" for t in tokens if t is not None]
        mdt = [m['symbol'] for m in metadata if m is not None]
        report_str = f"Tokens: {', '.join(tks)}, Metadata: {', '.join(mdt)}"
        logger.debug(report_str)

        for m in metadata:
            if m is None:
                continue
            for pattern in self.patterns:
                if (pattern in m.get('name', '').lower()
                        or pattern in m.get('symbol', '').lower()
                        or pattern in m.get('description', '').lower()):

                    logger.info(report_str)

                    # from scimitar.alerts import send_emergency_alert
                    # async send_emergency_alert(report_str)
