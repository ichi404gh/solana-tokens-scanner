# Solana Tokens Scanner

A Python application that monitors Solana blockchain transactions for specific AMM pool operations. The scanner identifies token pairs in transactions, retrieves their metadata, and filters them based on configured patterns.

## Features

- Real-time monitoring of Solana blockchain transactions
- Detection of token pairs used in AMM pool operations
- Metadata retrieval for identified tokens
- Pattern-based filtering for token reporting
- Support for different AMM configurations (Orca, Raydium CAMM)

## Requirements

- Python 3.10+ (tested on 3.13)
- Virtual environment (virtualenv)
- Solana RPC endpoint access
- Helius API key for token metadata retrieval (free tier)

## Installation

1. Clone the repository:
   ```sh
   git clone <repository-url>
   cd solana-tokens-scanner
   ```

2. Create and activate a virtual environment:
   ```sh
   python -m virtualenv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Run
   ```sh
   python main.py
   ```

## Environment Variables

Create a `.env` file in the project root with the following variables:
```dotenv
WS_ENDPOINT="wss://mainnet.helius-rpc.com/?api-key=<your key>"
RPC_ENDPOINT="https://mainnet.helius-rpc.com/?api-key=<your key>"

HELIUS_API_KEY="<helius api key>"
LOG_LEVEL=INFO # or DEBUG or WARNING 

SEARCH_PATTERN="barron,ivanka,tiffany,eric,donaldjr"
```
App is tested on the helius RPC node on the free tier, but might work well on any other node with 
a stable websocket connection, if fits into node's rate limits. App uses helius API to get token metadata.

## Configuration

App is working with `ORCA` and `Raydium concentrated liquidity` pools. Raydium tends to have much more
frequent events compared to Orca. To change AMM - edit `config.py`
```python
CONFIG = CONFIGS['orca']
#or
CONFIG = CONFIGS['raydium_CAMM']
```

