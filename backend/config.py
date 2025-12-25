NANOSECONDS = 1
MICROSECONDS = 1000 * NANOSECONDS
MILLISECONDS = 1000 * MICROSECONDS
SECONDS = 1000 * MILLISECONDS

MINE_RATE = 15 * SECONDS

# P2P defaults
P2P_HOST = "0.0.0.0"
P2P_PORT = 6000
P2P_SYNC_INTERVAL_SECONDS = 10

# Coin denomination
COIN_NAME = "PYTH"
UNIT_NAME = "pipu"
UNITS_PER_COIN = 100_000_000

# Monetary policy
#Supply total = reward_inicial × halving_blocks × 2
STARTING_REWARD_COINS = 12
STARTING_REWARD = STARTING_REWARD_COINS * UNITS_PER_COIN

# halving cadence (approx 2 years at 15s blocks -> 4.204.800 blocks)
HALVING_INTERVAL = 4_204_800
SUPPLY_MODEL = "halving"
INITIAL_SUPPLY = 0
TREASURY_ADDRESS = "treasury"
GENESIS_MESSAGE = "network-genesis"

MINING_REWARD_INPUT = { 'address': '+--official-mining-reward--+' }

# Foundation/treasury cut from each block reward 1%
FOUNDATION_ADDRESS = "c8102ec9be0227ce30dbf77fec8a4e19b9e701ea"
FOUNDATION_FEE_RATE = 0.01

# Fee policy with congestion-aware scaling (all values in smallest unit)
# Target: ~0.000025 COIN for a 250-byte tx at minimum congestion.
MIN_RELAY_FEE_PER_BYTE = 10   # baseline minimum per-byte fee
DYNAMIC_FEE_BASE_PER_BYTE = 20  # grows with congestion
FEE_CONGESTION_TARGET_TXS = 5000  # mempool size where fee doubles
FEE_MAX_MULTIPLIER = 8  # cap for congestion multiplier
MIN_ABSOLUTE_FEE = 10_000  # ~0.0001 COIN absolute floor to deter spam
TX_SIZE_INPUT_OVERHEAD = 100  # rough bytes overhead for inputs/metadata
MAX_TXS_PER_BLOCK = 500

# Miner control
AUTO_MINE_ENABLED = True
MINER_ADDRESS_OVERRIDE = None  # if set, reward transactions go here
MINER_NAME = "Miner"

# UI/refresh
AUTO_REFRESH_SECONDS = 1  # 0 disables auto refresh
