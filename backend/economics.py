from backend.config import (
    STARTING_REWARD,
    HALVING_INTERVAL,
    SUPPLY_MODEL,
    INITIAL_SUPPLY,
    TREASURY_ADDRESS,
    GENESIS_MESSAGE
)


def block_reward(height: int, start_reward: int = None, halving_interval: int = None, supply_model: str = None) -> int:
    """
    Compute the block reward for a given height (0-based, genesis is 0).
    """
    if height <= 0:
        return 0

    start = STARTING_REWARD if start_reward is None else start_reward
    halving = HALVING_INTERVAL if halving_interval is None else halving_interval
    model = SUPPLY_MODEL if supply_model is None else supply_model

    if model == "fixed":
        return start
    if model == "inflationary":
        return start

    era = max(0, (height - 1) // max(1, halving))
    reward = max(1, start >> era)

    return reward


def get_genesis_block_data():
    """
    Build the genesis block data with configurable supply information.
    """
    allocation_tx = {
        "id": "genesis-allocation",
        "output": {TREASURY_ADDRESS: INITIAL_SUPPLY},
        "input": {
            "timestamp": 0,
            "amount": INITIAL_SUPPLY,
            "address": "genesis",
            "public_key": "genesis",
            "signature": [0, 0],
            "type": "GENESIS",
            "note": GENESIS_MESSAGE,
            "supply_model": SUPPLY_MODEL,
            "start_reward": STARTING_REWARD,
            "halving_interval": HALVING_INTERVAL,
        },
    }

    return {
        "timestamp": 1,
        "last_hash": "genesis_last_hash",
        "hash": "genesis_hash",
        "data": [allocation_tx],
        "difficulty": 3,
        "nonce": "genesis_nonce",
    }
