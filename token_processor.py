import asyncio
import os
from dataclasses import dataclass
import traceback

from solana.rpc.api import Client
from solana.rpc.websocket_api import connect, SolanaWsClientProtocol
from solders.solders import Signature, Pubkey

from config import CONFIG
from metadata_processor import MetadataJob
from utils import keep_alive
import log

logger = log.logger.getChild(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAY = 3  # secs


@dataclass
class TokenJob:
    tx: Signature


class NoTransactionFoundError(Exception):
    pass


class TokenExtractionProcessor:
    def __init__(self, client: Client, result_queue: asyncio.Queue, shutdown_event: asyncio.Event):
        self.job_queue = asyncio.Queue()
        self.client = client
        self.result_queue = result_queue
        self.shutdown_event = shutdown_event

    def run(self):
        asyncio.create_task(self.worker())


    async def enqueue_token_job(self, tx: Signature):
        job = TokenJob(tx=tx)
        await self.job_queue.put(job)

    async def worker(self):
        logger.debug("Starting token extraction worker")

        async with connect(os.environ.get('WS_ENDPOINT')) as websocket:
            keep_alive_task = asyncio.create_task(keep_alive(websocket))

            while not self.shutdown_event.is_set():
                try:
                    job: TokenJob = await self.job_queue.get()
                    logger.debug(f"processing {job.tx}")
                    tokens = await self.process(job, websocket)
                    if tokens:
                        await self.result_queue.put(MetadataJob(tokens=tokens))
                except Exception as e:
                    logger.error(f"Unexpected error occurred: {e}")
                finally:
                    self.job_queue.task_done()
            keep_alive_task.cancel()

    async def process(self, job: TokenJob, websocket: SolanaWsClientProtocol) -> (Pubkey, Pubkey):
        try:
            logger.debug(f"subscribing to {job.tx}")
            await websocket.signature_subscribe(job.tx)
            response = await websocket.recv()
            sub_id = response[0].result if response and len(response) > 0 else None
            logger.debug(f"Successfully subscribed to websocket")

            resp = await websocket.recv()
            if resp[0].result.value.err:
                return None
            else:
                logger.debug(f"Transaction {job.tx} changed status to confirmed")

        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            return None
        finally:
            if 'sub_id' in locals() and sub_id is not None:
                try:
                    if sub_id in websocket.subscriptions:
                        del websocket.subscriptions[sub_id]
                    del sub_id
                except Exception as e:
                    logger.error(f"Error during unsubscribe: {e}")
                    return None

        for attempt in range(MAX_ATTEMPTS):
            try:
                tokens = self.get_tokens_from_pool_tx(job.tx)
                logger.debug(f"got tokens from tx")
                return tokens
            except NoTransactionFoundError:
                if attempt < MAX_ATTEMPTS - 1:
                    logger.debug(f"retrying {job.tx} attempt {attempt + 1}")
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    logger.error(f"Giving up on {str(job.tx)}")
                    return None
            except Exception as e:
                logger.error(f"Error processing {str(job.tx)} attempt {attempt}: {e}")
                traceback.print_exc()

        return None

    def get_tokens_from_pool_tx(self, tx_hash: Signature) -> tuple[Pubkey, Pubkey] | None:
        tx = self.client.get_transaction(tx_hash, max_supported_transaction_version=0, encoding="jsonParsed")
        logger.debug(tx)
        if not tx.value:
            raise NoTransactionFoundError()
        instructions = tx.value.transaction.transaction.message.instructions

        for ix in instructions:
            if ix.program_id == Pubkey.from_string(CONFIG.program_id):
                return ix.accounts[CONFIG.token_mint_0_idx], ix.accounts[CONFIG.token_mint_1_idx]
        logger.error("No token mint found, unexpectedly...")
        return None
