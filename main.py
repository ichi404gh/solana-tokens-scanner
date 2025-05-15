import asyncio
import datetime
import os
import signal

import dotenv
from solana.rpc.websocket_api import connect
from solana.rpc.api import Client
from solders.solders import Pubkey, RpcTransactionLogsFilterMentions

shutdown_event = asyncio.Event()

ORCA_PROGRAM_ID = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"  # Orca Whirlpool



def ask_exit(*args):
    print("got signal: exit")
    print(args)
    shutdown_event.set()
    print("Stopping loop...")

async def main():
    dotenv.load_dotenv()
    c = Client('https://api.mainnet-beta.solana.com')
    count = 0

    async with connect(os.environ.get('WS_ENDPOINT')) as websocket:
        await websocket.logs_subscribe(
            filter_=RpcTransactionLogsFilterMentions(
                Pubkey.from_string(ORCA_PROGRAM_ID),
            ),
        )

        print("Subscribed")
        first_resp = await websocket.recv()
        subscription_id = first_resp[0].result
        try:
            while not shutdown_event.is_set():
                print(f"\r[{datetime.datetime.now()}] logged {count}", end='')

                try:
                    next_resp = await asyncio.wait_for(websocket.recv(), timeout=2)
                    for resp in next_resp:
                        count += 1

                        log_lines = resp.result.value.logs
                        for line in log_lines:
                            if 'Instruction: InitializePool' in line:
                                print(resp.result.value.signature)
                                with open('results.txt', 'w') as f:
                                    f.write(str(resp.result.value.signature))

                except asyncio.TimeoutError:
                    continue
        finally:
            print("finishing jobs")
            await websocket.account_unsubscribe(subscription_id)
            response = await websocket.recv()
            print("Unsubscribed")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, ask_exit)
    signal.signal(signal.SIGTERM, ask_exit)
    asyncio.run(main())
