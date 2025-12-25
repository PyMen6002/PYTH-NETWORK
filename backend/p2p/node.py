import asyncio
import json
import random
import threading
from typing import Optional, Set
import time
import re

import websockets
from websockets import WebSocketServerProtocol

from backend.blockchain.block import Block
from backend.blockchain.blockchain import Blockchain
from backend.wallet.transaction import Transaction
from backend.wallet.transaction_pool import TransactionPool
from backend.util.log import log_debug, log_error, log_info, log_success, log_warn


MESSAGE_TYPES = {
    "HELLO": "HELLO",
    "PEERS": "PEERS",
    "REQUEST_CHAIN": "REQUEST_CHAIN",
    "CHAIN_SEGMENT": "CHAIN_SEGMENT",
    "BLOCK": "BLOCK",
    "TRANSACTION": "TRANSACTION",
    "PING": "PING",
}


class P2PNode:
    def __init__(self, host: str, port: int, blockchain: Blockchain, transaction_pool: TransactionPool, seeds=None, sync_interval=10):
        self.host = host
        self.port = port
        self.self_address = f"{self.host}:{self.port}"
        self.blockchain = blockchain
        self.transaction_pool = transaction_pool
        self.seeds = [s for s in (seeds or []) if self._is_valid_peer_address(s) and not self._is_self_address(s)]
        self.sync_interval = sync_interval
        self.connecting: Set[str] = set()
        self.failed_attempts = {}
        self.last_full_sync_request = 0.0
        self.synced = False
        self._synced_callbacks = []
        self._sync_change_callbacks = []

        self.loop = asyncio.new_event_loop()
        self.server = None
        self.peers: Set[WebSocketServerProtocol] = set()
        self.peer_addresses: Set[str] = set()
        for seed in (seeds or []):
            if self._is_valid_peer_address(seed) and not self._is_self_address(seed):
                self.peer_addresses.add(seed)

        self.thread = threading.Thread(target=self._run_loop, daemon=True)

    def start(self):
        if not self.thread.is_alive():
            log_info(f"[P2P] Starting node at ws://{self.self_address} seeds={self.seeds}")
            self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        server_coro = websockets.serve(self._handle_connection, self.host, self.port)
        self.server = self.loop.run_until_complete(server_coro)
        log_success(f"[P2P] Listening on ws://{self.self_address}")
        self.loop.create_task(self._connect_seeds())
        self.loop.create_task(self._periodic_sync())
        self.loop.run_forever()

    async def _handle_connection(self, websocket: WebSocketServerProtocol, _path):
        self._register_peer(websocket)
        await self._send_hello(websocket)

        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except Exception:
            pass
        finally:
            self._unregister_peer(websocket)

    def _register_peer(self, websocket: WebSocketServerProtocol):
        """
        Track a newly connected peer; if we already have a connection to the same address,
        drop the duplicate to avoid churn.
        """
        peer_address = None
        if websocket.remote_address:
            peer_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            # Avoid duplicate connections to the same peer (common when both dial each other).
            for peer in list(self.peers):
                if peer.remote_address and f"{peer.remote_address[0]}:{peer.remote_address[1]}" == peer_address:
                    # Drop the duplicate websocket and keep the existing one.
                    self.loop.create_task(websocket.close())
                    return
        self.peers.add(websocket)
        if peer_address:
            log_success(f"[P2P] Connected peer socket {peer_address}")

    def _unregister_peer(self, websocket: WebSocketServerProtocol):
        if websocket in self.peers:
            self.peers.remove(websocket)
            peer_address = None
            if websocket.remote_address:
                peer_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            if peer_address:
                log_warn(f"[P2P] Peer disconnected {peer_address}")
        if not self.peers and self.seeds:
            self._set_synced(False)

    async def _connect_seeds(self):
        for seed in self.seeds:
            await self._ensure_outbound_connection(seed)

    async def _ensure_outbound_connection(self, peer_address: str):
        if peer_address == self.self_address or self._is_self_address(peer_address) or not self._is_valid_peer_address(peer_address):
            return

        if peer_address in self.connecting:
            return
        # no quarantine logic

        for peer in list(self.peers):
            if peer.remote_address:
                existing_address = f"{peer.remote_address[0]}:{peer.remote_address[1]}"
                if existing_address == peer_address:
                    return

        failure_count = self.failed_attempts.get(peer_address, 0)
        if failure_count >= 6:
            log_warn(f"[P2P] Giving up on {peer_address} after {failure_count} failures")
            return

        uri = f"ws://{peer_address}"
        try:
            log_info(f"[P2P] Dialing peer {peer_address}")
            self.connecting.add(peer_address)
            websocket = await websockets.connect(uri)
            self._register_peer(websocket)
            await self._send_hello(websocket)
            self.loop.create_task(self._listen_outbound(websocket))
            log_debug(f"[P2P] Outbound connection established {peer_address}")
            self.failed_attempts[peer_address] = 0
        except Exception as exc:
            failure_count += 1
            self.failed_attempts[peer_address] = failure_count
            delay = min(30, 2 ** min(failure_count, 5))
            log_warn(f"[P2P] Failed to connect {peer_address} ({exc}); retrying in {delay}s (attempt {failure_count})")
            await asyncio.sleep(delay)
            self.loop.create_task(self._ensure_outbound_connection(peer_address))
        finally:
            if peer_address in self.connecting:
                self.connecting.remove(peer_address)

    async def _listen_outbound(self, websocket: WebSocketServerProtocol):
        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except Exception:
            pass
        finally:
            peer_address = None
            if websocket.remote_address:
                peer_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            self._unregister_peer(websocket)
            if peer_address:
                log_warn(f"[P2P] Lost outbound peer {peer_address}, scheduling reconnect")
                self.loop.create_task(self._ensure_outbound_connection(peer_address))

    async def _handle_message(self, websocket: WebSocketServerProtocol, raw_message: str):
        try:
            message = json.loads(raw_message)
        except ValueError:
            return

        msg_type = message.get("type")

        if msg_type == MESSAGE_TYPES["HELLO"]:
            peer_addr = message.get("address")
            if peer_addr and self._is_valid_peer_address(peer_addr) and not self._is_self_address(peer_addr):
                self.peer_addresses.add(peer_addr)
                log_debug(f"[P2P] HELLO from {peer_addr} height={message.get('height')}")

            remote_height = message.get("height", 0)
            remote_work = message.get("work", 0)
            remote_last_hash = message.get("last_hash")
            local_height = len(self.blockchain.chain) - 1
            local_work = self.blockchain.total_work()
            if (remote_height > local_height) or (remote_height == local_height and remote_work > local_work):
                log_info(f"[P2P] Remote chain ahead (h={remote_height}, work={remote_work}), local (h={local_height}, work={local_work}); requesting full sync")
                await self._request_chain(websocket, start=0)
            elif remote_height == local_height and remote_last_hash == self.blockchain.chain[-1].hash:
                self._set_synced(True)

            await self._send_peers(websocket)

        elif msg_type == MESSAGE_TYPES["PEERS"]:
            peers = message.get("peers", [])
            for peer in peers:
                if peer != self.self_address and self._is_valid_peer_address(peer) and not self._is_self_address(peer):
                    self.peer_addresses.add(peer)
                    self.loop.create_task(self._ensure_outbound_connection(peer))
            log_debug(f"[P2P] Received peers: {peers}")

        elif msg_type == MESSAGE_TYPES["REQUEST_CHAIN"]:
            start = message.get("start", 0)
            log_info(f"[P2P] Peer requested chain from height {start}")
            await self._send_chain_segment(websocket, start)

        elif msg_type == MESSAGE_TYPES["CHAIN_SEGMENT"]:
            start = message.get("start", 0)
            blocks_json = message.get("blocks", [])
            self._try_replace_chain(start, blocks_json)
            if start == len(self.blockchain.chain) and not blocks_json:
                self._set_synced(True)

        elif msg_type == MESSAGE_TYPES["BLOCK"]:
            block_json = message.get("block")
            if not block_json:
                return
            block = Block.from_json(block_json)
            potential_chain = self.blockchain.chain[:]
            potential_chain.append(block)

            try:
                self.blockchain.replace_chain(potential_chain)
                self.transaction_pool.clear_blockchain_transactions(self.blockchain)
                log_success(f"[P2P] Added new block height={len(self.blockchain.chain)-1} hash={block.hash[:8]}...")
                self._set_synced(True)
            except Exception as exc:
                self._record_invalid(websocket, reason=str(exc))
                self._set_synced(False)
                await self._request_full_sync_any(websocket)

        elif msg_type == MESSAGE_TYPES["TRANSACTION"]:
            tx_json = message.get("transaction")
            if not tx_json:
                return
            transaction = Transaction.from_json(tx_json)
            try:
                self.transaction_pool.set_transaction(transaction)
                log_info(f"[P2P] Received transaction {transaction.id[:8]}... from peer")
            except Exception as exc:
                log_warn(f"[P2P] Rejected incoming transaction: {exc}")
                log_warn(f"[P2P] Rejected incoming transaction: {exc}")
                pass

        elif msg_type == MESSAGE_TYPES["PING"]:
            await self._safe_send(websocket, {"type": "PONG"})

    async def _send_hello(self, websocket: WebSocketServerProtocol):
        await self._safe_send(websocket, {
            "type": MESSAGE_TYPES["HELLO"],
            "address": self.self_address,
            "height": len(self.blockchain.chain) - 1,
            "last_hash": self.blockchain.chain[-1].hash,
            "work": self.blockchain.total_work(),
        })

    async def _send_peers(self, websocket: WebSocketServerProtocol):
        await self._safe_send(websocket, {
            "type": MESSAGE_TYPES["PEERS"],
            "peers": list(self.peer_addresses),
        })

    async def _request_chain(self, websocket: WebSocketServerProtocol, start: int = 0):
        await self._safe_send(websocket, {
            "type": MESSAGE_TYPES["REQUEST_CHAIN"],
            "start": start,
        })

    async def _send_chain_segment(self, websocket: WebSocketServerProtocol, start: int = 0):
        if start < 0 or start > len(self.blockchain.chain):
            start = 0

        await self._safe_send(websocket, {
            "type": MESSAGE_TYPES["CHAIN_SEGMENT"],
            "start": start,
            "blocks": list(map(lambda block: block.to_json(), self.blockchain.chain[start:])),
        })
        log_debug(f"[P2P] Sent chain segment from {start} ({len(self.blockchain.chain[start:])} blocks)")

    def _try_replace_chain(self, start: int, blocks_json):
        if start > len(self.blockchain.chain):
            return

        potential_chain = self.blockchain.chain[:start] + list(
            map(lambda block_json: Block.from_json(block_json), blocks_json)
        )

        incoming_work = Blockchain.compute_work(potential_chain)
        local_work = self.blockchain.total_work()
        incoming_tip_hash = potential_chain[-1].hash if potential_chain else None
        local_tip_hash = self.blockchain.chain[-1].hash if self.blockchain.chain else None

        # Only attempt replacement if the incoming chain is actually better.
        if len(potential_chain) < len(self.blockchain.chain):
            return
        if len(potential_chain) == len(self.blockchain.chain) and incoming_work <= local_work:
            if incoming_tip_hash and incoming_tip_hash == local_tip_hash:
                self._set_synced(True)
            return

        try:
            self.blockchain.replace_chain(potential_chain)
            self.transaction_pool.clear_blockchain_transactions(self.blockchain)
            log_success(f"[P2P] Replaced chain from height {start}; new height {len(self.blockchain.chain)-1}")
            self._set_synced(True)
        except Exception as exc:
            self._record_invalid(None, reason=str(exc))
            self._set_synced(False)
            log_warn(f"[P2P] Failed to replace chain from {start}: {exc}")
            self.loop.create_task(self._request_full_sync_any())

    async def _safe_send(self, websocket: WebSocketServerProtocol, message: dict):
        try:
            await websocket.send(json.dumps(message))
        except Exception:
            self._unregister_peer(websocket)
            log_error("[P2P] Failed to send message to peer; dropping connection")

    async def _broadcast(self, message: dict, exclude: Optional[WebSocketServerProtocol] = None):
        peers_snapshot = list(self.peers)
        for peer in peers_snapshot:
            if peer == exclude:
                continue
            await self._safe_send(peer, message)

    def broadcast_block(self, block: Block):
        coro = self._broadcast({"type": MESSAGE_TYPES["BLOCK"], "block": block.to_json()})
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def broadcast_transaction(self, transaction: Transaction):
        coro = self._broadcast({"type": MESSAGE_TYPES["TRANSACTION"], "transaction": transaction.to_json()})
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def _periodic_sync(self):
        while True:
            await asyncio.sleep(self.sync_interval)
            peer = self._random_peer()
            if peer:
                log_debug("[P2P] Sync timer triggered; requesting chain from random peer")
                # Ask only for blocks we don't have yet; fall back to full sync elsewhere when needed.
                await self._request_chain(peer, start=len(self.blockchain.chain))

    def _random_peer(self) -> Optional[WebSocketServerProtocol]:
        if not self.peers:
            return None
        return random.choice(tuple(self.peers))

    def _record_invalid(self, websocket: Optional[WebSocketServerProtocol], reason: str = ""):
        # no quarantine; optionally log
        if websocket and websocket.remote_address:
            peer_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            log_warn(f"[P2P] Invalid data from {peer_address} reason={reason}")
        else:
            log_warn(f"[P2P] Invalid data reason={reason}")
        self._set_synced(False)
        self.loop.create_task(self._request_full_sync_any(websocket))
        self._maybe_drop_bad_transaction(reason)
        self._purge_mempool(reason)

    def on_synced(self, callback):
        """
        Register a callback invoked once when the node transitions to a synced state.
        """
        self._synced_callbacks.append(callback)

    def on_sync_change(self, callback):
        """
        Register a callback invoked on any sync status change (bool argument).
        """
        self._sync_change_callbacks.append(callback)

    def _set_synced(self, value: bool):
        prev = self.synced
        self.synced = value
        if prev == value:
            return

        for cb in list(self._sync_change_callbacks):
            self._invoke_callback(cb, value)

        if value:
            for cb in list(self._synced_callbacks):
                self._invoke_callback(cb)

    @staticmethod
    def _invoke_callback(callback, *args):
        try:
            callback(*args)
        except Exception as exc:
            log_warn(f"[P2P] Sync callback failed: {exc}")

    async def _request_full_sync_any(self, websocket: Optional[WebSocketServerProtocol] = None):
        """
        Trigger a full chain sync request, rate-limited to avoid floods.
        """
        now = time.time()
        if now - self.last_full_sync_request < 5:
            return
        self.last_full_sync_request = now

        target = websocket if websocket and websocket in self.peers else self._random_peer()
        if target:
            await self._request_chain(target, start=0)

    def _maybe_drop_bad_transaction(self, reason: str):
        """
        If an invalid-chain reason references a specific transaction id, drop it from the mempool
        to avoid re-mining known-bad transactions.
        """
        if not reason:
            return
        match = re.search(r"Transaction\s+([0-9a-fA-F]{8,})", reason)
        if match:
            txid = match.group(1)
            if txid in self.transaction_pool.transaction_map:
                self.transaction_pool.transaction_map.pop(txid, None)
                log_warn(f"[P2P] Dropped bad transaction {txid} from mempool due to validation error")

    def _purge_mempool(self, reason: str = ""):
        """
        Drop all pending transactions when we fail to sync/validate, to avoid re-mining junk that keeps chains diverging.
        """
        if hasattr(self, "transaction_pool") and getattr(self.transaction_pool, "transaction_map", None) is not None:
            self.transaction_pool.transaction_map.clear()
            if reason:
                log_warn(f"[P2P] Cleared mempool after sync/validation failure: {reason}")
            else:
                log_warn("[P2P] Cleared mempool after sync/validation failure")

    @staticmethod
    def _is_valid_peer_address(address: str) -> bool:
        """
        Rejects invalid or wildcard addresses (e.g., 0.0.0.0) to avoid dialing garbage peers.
        """
        if not address or ":" not in address:
            return False
        host, port = address.split(":", 1)
        if host.strip() in ("", "0.0.0.0"):
            return False
        try:
            int(port)
        except ValueError:
            return False
        return True

    def _is_self_address(self, address: str) -> bool:
        """
        Detect whether a given address points back to this node (handles localhost/0.0.0.0).
        """
        if not address or ":" not in address:
            return False
        host, port = address.split(":", 1)
        try:
            port_int = int(port)
        except ValueError:
            return False
        if port_int != self.port:
            return False
        normalized_host = host.strip().lower()
        self_host = self.host.strip().lower()
        local_hosts = {"0.0.0.0", "127.0.0.1", "localhost"}
        if normalized_host == self_host:
            return True
        if normalized_host in local_hosts and self_host in local_hosts:
            return True
        return False
