import asyncio
import datetime
import os
import signal
import logging
from dataclasses import dataclass

import dotenv
from solana.rpc import commitment
from solana.rpc.websocket_api import connect
from solana.rpc.api import Client
from solders.solders import Pubkey, RpcTransactionLogsFilterMentions, Signature

from metadata import MetadataProcessor

"""
TODO:
+ extract tokens from tx
+ get token names
    - handle in pairs
    - report, filter required patterns
- error handling
- loop break
+ add logging
"""

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', )
logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)

shutdown_event = asyncio.Event()


@dataclass
class AMMConfig:
    program_id: str
    token_mint_0_idx: int
    token_mint_1_idx: int
    log_pattern: str


CONFIGS = {
    'orca': AMMConfig(
        program_id="whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
        token_mint_0_idx=1,
        token_mint_1_idx=2,
        log_pattern='Instruction: InitializePool'
    ),
    'raydium_CAMM': AMMConfig(
        program_id="CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
        token_mint_0_idx=3,
        token_mint_1_idx=4,
        log_pattern='Program log: Instruction: CreatePool'
    ),
}

CONFIG = CONFIGS['raydium_CAMM']


def ask_exit(*args):
    signal_map = {signal.SIGINT: 'SIGINT', signal.SIGTERM: 'SIGTERM'}

    logger.info(f"got signal: {signal_map[args[0]]}")
    shutdown_event.set()
    logger.info("Stopping loop...")


async def main():
    try:
        dotenv.load_dotenv()
        mp = MetadataProcessor()
        mp.run()

        c = Client('https://api.mainnet-beta.solana.com')
        count = 0

        async with connect(os.environ.get('WS_ENDPOINT')) as websocket:
            try:
                await websocket.logs_subscribe(
                    filter_=RpcTransactionLogsFilterMentions(
                        Pubkey.from_string(CONFIG.program_id),
                    ),
                    commitment=commitment.Confirmed
                )
                logger.info("Successfully subscribed to websocket")

                response = await websocket.recv()

                subscription_id = response[0].result

                while not shutdown_event.is_set():
                    if count % 1000 == 0:
                        logger.debug(f"Processed {count} transactions")

                    try:
                        next_resp = await asyncio.wait_for(websocket.recv(), timeout=2)
                        for resp in next_resp:
                            count += 1
                            log_lines = resp.result.value.logs
                            for line in log_lines:
                                if CONFIG.log_pattern in line:
                                    await process_log_response(resp, c, mp)

                    except asyncio.TimeoutError:
                        continue
                    except asyncio.exceptions.IncompleteReadError:
                        logger.error("Connection was interrupted. Attempting to reconnect...")
                        break
                    except Exception as e:
                        logger.error(f"Unexpected error occurred: {e}")
                        break

            finally:
                logger.info("Disconnecting from WebSocket...")
                if 'subscription_id' in locals():
                    await websocket.logs_unsubscribe(subscription_id)
                    await websocket.recv()
                logger.info("Successfully unsubscribed from WebSocket")

    finally:
        # Cancel all running tasks
        for task in asyncio.all_tasks() - {asyncio.current_task()}:
            task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*[task for task in asyncio.all_tasks() - {asyncio.current_task()}],
                           return_exceptions=True)


def get_tokens_from_pool_tx(client: Client, tx_hash: Signature):
    tx = client.get_transaction(tx_hash, max_supported_transaction_version=0, commitment=commitment.Confirmed,
                              encoding="jsonParsed")
    logger.debug(tx)
    instructions = tx.value.transaction.transaction.message.instructions

    for ix in instructions:
        if ix.program_id == Pubkey.from_string(CONFIG.program_id):
            return ix.accounts[CONFIG.token_mint_0_idx], ix.accounts[CONFIG.token_mint_1_idx]  # from IDL


async def process_log_response(resp, client: Client, mp: MetadataProcessor):
    logger.debug("Processing transaction " + str(resp.result.value.signature))
    with open('results.txt', 'a') as f:
        f.write(datetime.datetime.now().isoformat() + ' - ')
        f.write(str(resp.result.value.signature) + '\n')
    with open('logs.txt', 'a') as f:
        f.write(str(resp) + '\n')

    tokens = get_tokens_from_pool_tx(client, resp.result.value.signature)
    await mp.enqueue_metadata_job(tokens)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, ask_exit)
    signal.signal(signal.SIGTERM, ask_exit)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupt signal received. Shutting down...")