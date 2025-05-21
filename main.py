import asyncio
import datetime
import os
import signal
import logging

import dotenv
from solana.rpc import commitment
from solana.rpc.websocket_api import connect
from solana.rpc.api import Client
from solders.solders import Pubkey, RpcTransactionLogsFilterMentions

from config import CONFIG
from metadata_processor import MetadataProcessor
from token_processor import TokenExtractionProcessor
from log import logger
from utils import keep_alive


shutdown_event = asyncio.Event()

def ask_exit(*args):
    signal_map = {signal.SIGINT: 'SIGINT', signal.SIGTERM: 'SIGTERM'}

    logger.info(f"got signal: {signal_map[args[0]]}")
    shutdown_event.set()
    logger.info("Stopping loop...")


async def main():
    try:
        c = Client(os.environ.get('RPC_ENDPOINT'))

        tokens_queue = asyncio.Queue()

        tp = TokenExtractionProcessor(client=c, result_queue=tokens_queue, shutdown_event=shutdown_event)
        tp.run()

        mp = MetadataProcessor(job_queue=tokens_queue, shutdown_event=shutdown_event)
        mp.run()

        count = 0

        async with connect(os.environ.get('WS_ENDPOINT')) as websocket:
            keep_alive_task = asyncio.create_task(keep_alive(websocket))
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
                        next_resp = await websocket.recv()
                        for resp in next_resp:
                            count += 1
                            log_lines = resp.result.value.logs
                            for line in log_lines:
                                if CONFIG.log_pattern in line:
                                    await process_log_response(resp, tp)
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
                keep_alive_task.cancel()


    finally:
        # Cancel all running tasks
        for task in asyncio.all_tasks() - {asyncio.current_task()}:
            task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*[task for task in asyncio.all_tasks() - {asyncio.current_task()}],
                           return_exceptions=True)


async def process_log_response(resp, tp: TokenExtractionProcessor):
    logger.debug("Processing transaction " + str(resp.result.value.signature))
    await tp.enqueue_token_job(resp.result.value.signature)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, ask_exit)
    signal.signal(signal.SIGTERM, ask_exit)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupt signal received. Shutting down...")