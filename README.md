# PYTH NETWORK Blockchain (Python)

## Overview
Blockchain made with Python:
- Fully decentralized P2P network system.
- Block reward and dynamic commissions.
- Wallet starts at 0, ECDSA secp256k1 Keys and signed transactions.
- Configurable monetary policy (halving/fixed/inflationary) and parameterized genesis.
- Mempool with validation/double-spend prevention and robust balance calculation.

## Requirements
- Python 3.11+ (recommended)
- pip/venv

## Installation
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell
pip install -r requierements.txt
```

## Run nodes
Bootstrap a node:
```bash
<<<<<<< HEAD
LINUX:
API_PORT=5000 P2P_PORT=6000 python -m backend.app

Windows (powershell):
$env:API_PORT="5000"; $env:P2P_HOST="localhost"; $env:P2P_PORT="6000"; python -m backend.app
=======
API_PORT=5000 P2P_PORT=6000 python -m backend.app

Remove-Item Env:PEER -ErrorAction SilentlyContinue
Remove-Item Env:P2P_SEEDS -ErrorAction SilentlyContinue
$env:API_PORT="5000"; $env:P2P_HOST="localhost"; $env:P2P_PORT="6000"; python -m backend.app

$env:PEER="True"; $env:API_PORT="5001"; $env:P2P_HOST="localhost"; $env:P2P_PORT="6001"; $env:P2P_SEEDS="localhost:6000"; python -m backend.app
>>>>>>> 07fdc29 (up1)
```

Start extra nodes pointing to the seed (same machine or others, adjust IP):
```bash
<<<<<<< HEAD
Linux:
PEER=True API_PORT=5001 P2P_PORT=6001 P2P_SEEDS=localhost:6000 python -m backend.app
# On another machine:
# PEER=True API_PORT=5000 P2P_PORT=6000 P2P_SEEDS=<seed_ip>:6000 python -m backend.app
Windows (powershell):
$env:PEER="True"; $env:API_PORT="5001"; $env:P2P_HOST="localhost"; $env:P2P_PORT="6001"; $env:P2P_SEEDS="localhost:6000"; python -m backend.app

=======
PEER=True API_PORT=5001 P2P_PORT=6001 P2P_SEEDS=localhost:6000 python -m backend.app
# On another machine:
# PEER=True API_PORT=5000 P2P_PORT=6000 P2P_SEEDS=<seed_ip>:6000 python -m backend.app
>>>>>>> 07fdc29 (up1)
```

Useful variables:
- `API_PORT`: Flask HTTP port.
- `P2P_PORT`: P2P websocket port (per node).
- `P2P_SEEDS`: comma-separated `host:port` list to connect at startup.
- `P2P_HOST`: P2P listen host (default `0.0.0.0`).
- `P2P_SYNC_INTERVAL_SECONDS`: how often to request sync.

## Quick API
- `GET /blockchain` → full chain in JSON.
- `GET /blockchain/mine` → mine a block with highest-fee/byte mempool txs; reward = `block_reward(height) + fees`.
- `POST /wallet/create` → create a wallet (non-miner) returning `address` and `public_key` (add `{"include_private_key":true}` to also receive the private key).
- `POST /wallet/transact` → body: `{"recipient":"addr","amount":10}`. Fee auto-computed by size (>= `MIN_RELAY_FEE_PER_BYTE * tx_size_bytes`).
- `GET /wallet/info` → local node wallet address and balance (no private key exposure).

## How it works
- **Blocks**: Proof-of-Work with difficulty adjusted by `MINE_RATE`. Genesis generated from `backend/economics.py` (supports initial allocation).
- **Transactions**: `input` (timestamp, amount, address, public_key, signature, fee) + `output` (recipient map). Fees deducted from sender and validated per byte.
- **Reward**: `block_reward(height)` per `SUPPLY_MODEL` (`halving`, `fixed`, `inflationary`) + sum of block fees. Enforced in `Blockchain.is_valid_transaction_chain`.
- **Wallets**: ECDSA secp256k1 keys, balance computed scanning chain from newest to oldest (latest spend overrides, add later receipts).
- **Mempool**: `TransactionPool` validates txs, prevents double spend per address in mempool, sorts by fee/byte. `MAX_TXS_PER_BLOCK` limits mined txs.
- **P2P**: `backend/p2p/node.py` uses websockets for block/tx gossip, peer exchange, and incremental sync (`REQUEST_CHAIN/CHAIN_SEGMENT`).

## Monetary policy (backend/config.py + backend/economics.py)
- `SUPPLY_MODEL`: `halving` | `fixed` | `inflationary`
- `STARTING_REWARD`, `HALVING_INTERVAL`, `INFLATION_RATE`
- `INITIAL_SUPPLY`, `TREASURY_ADDRESS`, `GENESIS_MESSAGE`
- Per-height reward is computed in `block_reward(height)` and enforced per block.

## Tests
```bash
pytest
```

## Security notes
- Private keys are not returned by default. If you explicitly request them (wallet creation), store them off-node or encrypted.
- Enable TLS on P2P transport if exposed to the internet.
- Limit `P2P_SEEDS` to trusted peers in closed environments.

## License
MIT. See `LICENSE` for details.
