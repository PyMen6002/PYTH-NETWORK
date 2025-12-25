import os
import random
import datetime

from flask import Flask, jsonify, request, render_template, abort
from cryptography.hazmat.primitives import serialization

from backend.blockchain.blockchain import Blockchain
from backend.wallet.wallet import Wallet
from backend.wallet.transaction import Transaction
from backend.wallet.transaction_pool import TransactionPool
from backend.p2p.node import P2PNode
from backend.economics import block_reward
from backend.config import (
    P2P_HOST,
    P2P_PORT,
    P2P_SYNC_INTERVAL_SECONDS,
    MINING_REWARD_INPUT,
    MAX_TXS_PER_BLOCK,
    AUTO_MINE_ENABLED,
    MINER_ADDRESS_OVERRIDE,
    MINER_NAME,
    AUTO_REFRESH_SECONDS,
    FOUNDATION_ADDRESS,
    FOUNDATION_FEE_RATE,
    COIN_NAME,
    UNIT_NAME,
    UNITS_PER_COIN,
)
from backend.util.log import log_info, log_success, log_warn
import threading
import time

app = Flask(__name__)
blockchain = Blockchain()
wallet = Wallet(blockchain)
transaction_pool = TransactionPool(blockchain)
peer_mode_env = os.environ.get('PEER') == 'True'
auto_mine_enabled = AUTO_MINE_ENABLED
miner_address_override = MINER_ADDRESS_OVERRIDE
miner_name = MINER_NAME
auto_mine_stop_event = threading.Event()
auto_mine_thread = None
mining_lock = threading.Lock()
refresh_interval_seconds = AUTO_REFRESH_SECONDS

# P2P setup
ROOT_PORT = int(os.environ.get('API_PORT', 5000))
PORT = ROOT_PORT

if peer_mode_env:
    PORT = random.randint(5001, 6000)

p2p_port = int(os.environ.get('P2P_PORT', P2P_PORT + (PORT - ROOT_PORT)))
seed_peers = [peer for peer in os.environ.get('P2P_SEEDS', '').split(',') if peer]
require_sync_before_mining = peer_mode_env or bool(seed_peers)

log_info(f"[HTTP] API port={PORT} peer_mode={peer_mode_env}")
log_info(f"[P2P] Host={P2P_HOST} port={p2p_port} seeds={seed_peers or ['<none>']}")

p2p_node = P2PNode(
    P2P_HOST,
    p2p_port,
    blockchain,
    transaction_pool,
    seeds=seed_peers,
    sync_interval=P2P_SYNC_INTERVAL_SECONDS
)
p2p_node.start()
log_success(f"[NODE] Node online | wallet={wallet.address[:8]}... | chain_height={len(blockchain.chain)-1}")


def mine_once():
    with mining_lock:
        prioritized = transaction_pool.prioritized_transactions(limit=MAX_TXS_PER_BLOCK)
        accepted = []
        pending_spent = {}
        dropped_ids = []

        def _net_spend(tx, sender_address):
            spend = tx.input.get("amount", 0)
            change_back = tx.output.get(sender_address, 0)
            return max(0, spend - change_back)

        for tx in prioritized:
            # Skip any reward/genesis noise that might be in the pool (shouldn't happen).
            if tx.input == MINING_REWARD_INPUT or tx.input.get("type") == "GENESIS":
                dropped_ids.append(tx.id)
                continue

            sender = tx.input.get("address")
            if not sender:
                dropped_ids.append(tx.id)
                continue

            available = Wallet.calculate_balance(blockchain, sender) - pending_spent.get(sender, 0)
            sender_net_spend = _net_spend(tx, sender)
            if sender_net_spend > available:
                log_warn(f"[MINER] Dropping tx {tx.id[:8]}: input exceeds current balance for {sender[:8]}...")
                dropped_ids.append(tx.id)
                continue

            accepted.append(tx)
            pending_spent[sender] = pending_spent.get(sender, 0) + sender_net_spend

        # Remove dropped transactions from the mempool to avoid reprocessing invalid ones.
        for txid in dropped_ids:
            transaction_pool.transaction_map.pop(txid, None)

        transaction_data = [tx.to_json() for tx in accepted]

        fees = sum([
            tx.input.get("fee", 0)
            for tx in accepted
            if tx.input != MINING_REWARD_INPUT
            and tx.input.get("type") != "GENESIS"
        ])
        policy = blockchain.policy()
        reward_amount = block_reward(
            len(blockchain.chain),
            start_reward=policy["start_reward"],
            halving_interval=policy["halving_interval"],
            supply_model=policy["supply_model"],
        ) + fees
        reward_address = miner_address_override or wallet.address
        foundation_cut = 0
        if FOUNDATION_ADDRESS and FOUNDATION_FEE_RATE > 0:
            foundation_cut = int(reward_amount * FOUNDATION_FEE_RATE)
            foundation_cut = min(foundation_cut, reward_amount)
        miner_take = reward_amount - foundation_cut
        reward_outputs = {}
        if miner_take > 0:
            reward_outputs[reward_address] = miner_take
        if foundation_cut > 0:
            reward_outputs[FOUNDATION_ADDRESS] = reward_amount - miner_take

        transaction_data.append(Transaction(input=MINING_REWARD_INPUT, output=reward_outputs).to_json())
        blockchain.add_block(transaction_data)

        block = blockchain.chain[-1]
        log_success(f"[MINER] Mined block height={len(blockchain.chain)-1} txs={len(transaction_data)} reward={reward_amount} to={reward_address[:8]}... foundation={foundation_cut}")
        p2p_node.broadcast_block(block)
        transaction_pool.clear_blockchain_transactions(blockchain)
        return block


def _auto_mine_loop():
    while not auto_mine_stop_event.is_set():
        try:
            mine_once()
        except Exception as exc:
            log_warn(f"[MINER] Auto-mine iteration skipped: {exc}")
        auto_mine_stop_event.wait(5)


def start_auto_miner():
    global auto_mine_thread
    if auto_mine_thread and auto_mine_thread.is_alive():
        return
    auto_mine_stop_event.clear()
    auto_mine_thread = threading.Thread(target=_auto_mine_loop, daemon=True)
    auto_mine_thread.start()
    log_info(f"[MINER] Auto-miner started name={miner_name} address={miner_address_override or wallet.address}")


def stop_auto_miner():
    auto_mine_stop_event.set()
    log_info("[MINER] Auto-miner stopped")


def _start_miner_if_ready(log_wait: bool = False):
    """
    Start the auto-miner only when the node is synced (when required).
    """
    if not auto_mine_enabled:
        return
    if require_sync_before_mining and not p2p_node.synced:
        if log_wait:
            log_info("[MINER] Waiting for chain sync before starting auto-miner")
        return
    start_auto_miner()


def _handle_sync_change(is_synced: bool):
    if not auto_mine_enabled:
        return
    if is_synced:
        _start_miner_if_ready()
    else:
        stop_auto_miner()


p2p_node.on_synced(_start_miner_if_ready)
p2p_node.on_sync_change(_handle_sync_change)

if auto_mine_enabled:
    if require_sync_before_mining:
        _start_miner_if_ready(log_wait=True)
    else:
        start_auto_miner()


@app.route("/")
def route_default():
    return render_template("index.html")

@app.route("/wallets")
def route_wallets_page():
    return render_template("wallets.html")

@app.route("/transactions")
def route_transactions_page():
    return render_template("transactions.html")

@app.route("/config_page")
def route_config_page():
    return render_template("config.html")

@app.route("/config", methods=["GET", "POST"])
def route_config():
    global auto_mine_enabled, miner_address_override, miner_name, refresh_interval_seconds
    if request.method == "GET":
        return jsonify({
            "auto_mine": auto_mine_enabled,
            "miner_address": miner_address_override or wallet.address,
            "default_wallet_address": wallet.address,
            "miner_name": miner_name,
            "refresh_interval_seconds": refresh_interval_seconds,
            "coin_name": COIN_NAME,
            "unit_name": UNIT_NAME,
            "units_per_coin": UNITS_PER_COIN,
        })

    body = request.get_json() or {}
    auto_mine_enabled = bool(body.get("auto_mine", auto_mine_enabled))
    miner_address_override = body.get("miner_address") or None
    miner_name = body.get("miner_name") or miner_name
    try:
        refresh_interval_seconds = max(0, int(body.get("refresh_interval_seconds", refresh_interval_seconds)))
    except (TypeError, ValueError):
        refresh_interval_seconds = refresh_interval_seconds

    if auto_mine_enabled:
        _start_miner_if_ready(log_wait=True)
    else:
        stop_auto_miner()

    return jsonify({
        "auto_mine": auto_mine_enabled,
        "miner_address": miner_address_override or wallet.address,
        "miner_name": miner_name,
        "refresh_interval_seconds": refresh_interval_seconds,
        "coin_name": COIN_NAME,
        "unit_name": UNIT_NAME,
        "units_per_coin": UNITS_PER_COIN,
    })

@app.route("/block/<block_hash>")
def route_block_detail(block_hash):
    target = None
    idx = None
    for block in blockchain.chain:
        if block.hash == block_hash:
            target = block
            idx = blockchain.chain.index(block)
            break
    if not target:
        abort(404)
    prev_hash = blockchain.chain[idx-1].hash if idx is not None and idx > 0 else None
    next_hash = blockchain.chain[idx+1].hash if idx is not None and idx < len(blockchain.chain)-1 else None
    human_time = datetime.datetime.fromtimestamp(target.timestamp / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S")
    return render_template("block.html", block=target, chain_height=len(blockchain.chain)-1, prev_hash=prev_hash, next_hash=next_hash, human_time=human_time)


@app.route("/address/<address>")
def route_address_detail(address):
    balance = Wallet.calculate_balance(blockchain, address)
    return render_template("address.html", address=address, balance=balance)


@app.route("/blockchain")
def route_blockchain():
    return jsonify(blockchain.to_json())


@app.route("/blockchain/mine")
def route_blockchain_mine():
    try:
        block = mine_once()
        return jsonify(block.to_json())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route('/wallet/transact', methods=['POST'])
def route_wallet_transact():
    transaction_data = request.get_json()

    try:
        transaction = Transaction(
            wallet,
            transaction_data['recipient'],
            transaction_data['amount'],
            mempool_size=len(transaction_pool.transaction_map),
        )
        log_info(f"[TX] Creating transaction to={transaction_data['recipient']} amount={transaction_data['amount']}")

        transaction_pool.set_transaction(transaction)
    except Exception as exc:
        log_warn(f"[TX] Transaction rejected: {exc}")
        return jsonify({"error": str(exc)}), 400

    p2p_node.broadcast_transaction(transaction)
    log_success(f"[TX] Broadcast transaction {transaction.id[:8]}...")

    return jsonify(transaction.to_json())

@app.route("/wallet/estimate_fee", methods=["GET"])
def route_wallet_estimate_fee():
    recipient = request.args.get("recipient") or wallet.address
    try:
        amount = float(request.args.get("amount", 0))
    except ValueError:
        return jsonify({"error": "invalid amount"}), 400

    try:
        if amount <= 0:
            return jsonify({"error": "amount must be positive"}), 400

        balance = wallet.balance
        provisional_change = balance - amount
        if provisional_change < 0:
            provisional_change = 0

        dummy_output = {recipient: amount, wallet.address: provisional_change}
        fee = Transaction.compute_fee(dummy_output, mempool_size=len(transaction_pool.transaction_map))
        insufficient = (amount + fee) > balance
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "fee": fee,
        "total_required": amount + fee,
        "balance": wallet.balance,
        "insufficient": insufficient
    })


@app.route("/wallet/info")
def route_wallet_info():
    log_info(f"[WALLET] Info requested addr={wallet.address[:8]}... balance={wallet.balance}")
    return jsonify({
        "address": wallet.address,
        "balance": wallet.balance,
        "public_key": wallet.public_key,
        "private_key": wallet.private_key.private_numbers().private_value.to_bytes(32, 'big').hex()
    })

@app.route("/wallet/balance")
def route_wallet_balance():
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "address is required"}), 400
    log_info(f"[WALLET] Balance requested for {address[:8]}...")
    balance = Wallet.calculate_balance(blockchain, address)
    return jsonify({"address": address, "balance": balance})


def _tx_matches_address(tx_json: dict, address: str) -> bool:
    if not address:
        return True
    address = address.lower()
    try:
        if tx_json.get("input", {}).get("address", "").lower() == address:
            return True
    except Exception:
        pass
    try:
        for out_addr in (tx_json.get("output") or {}):
            if out_addr.lower() == address:
                return True
    except Exception:
        pass
    return False


def _tx_status_entry(tx_json: dict, status: str, height: int = None, block_hash: str = None, timestamp: int = None):
    return {
        "id": tx_json.get("id"),
        "status": status,
        "height": height,
        "block_hash": block_hash,
        "timestamp": timestamp or tx_json.get("input", {}).get("timestamp"),
        "input": tx_json.get("input"),
        "output": tx_json.get("output"),
        "fee": tx_json.get("input", {}).get("fee", 0),
        "type": tx_json.get("input", {}).get("type"),
    }


@app.route("/transactions/feed")
def route_transactions_feed():
    """
    Return recent confirmed transactions and current mempool with status hints.
    Optional params:
    - address: filter by address (input or output)
    - limit: max confirmed txs to return (default 50)
    """
    address = (request.args.get("address") or "").strip()
    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
    except (TypeError, ValueError):
        limit = 50

    seen_ids = set()
    mempool_entries = []
    for tx in transaction_pool.prioritized_transactions():
        tx_json = tx.to_json()
        if not _tx_matches_address(tx_json, address):
            continue
        mempool_entries.append(_tx_status_entry(tx_json, status="mempool"))
        seen_ids.add(tx.id)

    confirmed_entries = []
    for height in range(len(blockchain.chain) - 1, -1, -1):
        if len(confirmed_entries) >= limit:
            break
        block = blockchain.chain[height]
        for tx_json in block.data:
            txid = tx_json.get("id")
            if txid in seen_ids:
                continue
            if not _tx_matches_address(tx_json, address):
                continue
            confirmed_entries.append(
                _tx_status_entry(
                    tx_json,
                    status="confirmed",
                    height=height,
                    block_hash=block.hash,
                    timestamp=block.timestamp
                )
            )
            seen_ids.add(txid)
            if len(confirmed_entries) >= limit:
                break

    return jsonify({
        "mempool": mempool_entries,
        "confirmed": confirmed_entries,
        "height": len(blockchain.chain) - 1
    })


@app.route("/transactions/<txid>")
def route_transaction_detail(txid):
    address_filter = (request.args.get("address") or "").strip()
    # Check mempool first
    tx = transaction_pool.transaction_map.get(txid)
    if tx and _tx_matches_address(tx.to_json(), address_filter):
        entry = _tx_status_entry(tx.to_json(), status="mempool")
        entry["confirmations"] = 0
        return jsonify(entry)

    for height, block in enumerate(blockchain.chain):
        for tx_json in block.data:
            if tx_json.get("id") == txid and _tx_matches_address(tx_json, address_filter):
                confirmations = (len(blockchain.chain) - 1) - height
                entry = _tx_status_entry(
                    tx_json,
                    status="confirmed",
                    height=height,
                    block_hash=block.hash,
                    timestamp=block.timestamp
                )
                entry["confirmations"] = confirmations
                return jsonify(entry)

    return jsonify({"error": "transaction not found", "id": txid, "status": "unknown"}), 404


@app.route("/wallet/create", methods=["POST"])
def route_wallet_create():
    """
    Create a standalone wallet (no mining needed) and return keys.
    """
    new_wallet = Wallet(blockchain)
    log_info(f"[WALLET] Created standalone wallet {new_wallet.address[:8]}...")
    response = {
        "address": new_wallet.address,
        "public_key": new_wallet.public_key,
        "private_key": new_wallet.private_key.private_numbers().private_value.to_bytes(32, 'big').hex()
    }
    return jsonify(response)

@app.route("/wallet/import", methods=["POST"])
def route_wallet_import():
    """
    Import an existing wallet via hex or PEM private key.
    If set_active is True, replace the node wallet. Private keys are not echoed back.
    """
    global wallet
    body = request.get_json() or {}
    private_key = body.get("private_key")
    set_active = body.get("set_active", False)
    if not private_key:
        return jsonify({"error": "private_key is required"}), 400

    try:
        imported_wallet = Wallet.from_private_key(private_key, blockchain)
    except Exception as exc:
        return jsonify({"error": f"Invalid private key: {exc}"}), 400

    if set_active:
        global wallet
        wallet = imported_wallet
        log_success(f"[WALLET] Imported wallet set active {wallet.address[:8]}...")
    else:
        log_info(f"[WALLET] Imported wallet {imported_wallet.address[:8]}... (not active)")

    return jsonify({
        "address": imported_wallet.address,
        "public_key": imported_wallet.public_key,
        "set_active": set_active
    })


if __name__ == '__main__':
    app.run(port=PORT)
