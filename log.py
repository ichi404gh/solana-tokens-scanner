import logging
import os

import dotenv

dotenv.load_dotenv()
LOGLEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("solana_scanner")
logger.setLevel(LOGLEVEL)