from dataclasses import dataclass


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
CONFIG = CONFIGS['orca']
