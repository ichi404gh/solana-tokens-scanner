import asyncio
import signal

from solana.rpc.websocket_api import connect

shutdown_event = asyncio.Event()

def ask_exit(*args):
    print("got signal: exit")
    print(args)
    shutdown_event.set()
    print("Stopping loop...")

async def main():
    async with connect("wss://api.devnet.solana.com") as websocket:
        await websocket.logs_subscribe()
        print("Subscribed")
        first_resp = await websocket.recv()
        subscription_id = first_resp[0].result
        while not shutdown_event.is_set():
            next_resp = await websocket.recv()
            print(next_resp)

        await websocket.logs_unsubscribe(subscription_id)
        print("Unsubscribed")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, ask_exit)
    signal.signal(signal.SIGTERM, ask_exit)
    asyncio.run(main())
