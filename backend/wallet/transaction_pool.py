import json
from backend.wallet.transaction import Transaction
from backend.wallet.wallet import Wallet
from backend.config import MINING_REWARD_INPUT


class TransactionPool:
    def __init__(self, blockchain=None):
        self.transaction_map = {}
        # Optional reference to the blockchain for balance checks on mempool admission.
        self.blockchain = blockchain

    def set_transaction(self, transaction):
        """
        Store a validated transaction, rejecting double spends from the same sender in the mempool.
        """
        Transaction.is_valid_transaction(transaction)
        # Allow multiple pending txs from same sender, but ensure aggregate spend fits balance.
        if self.blockchain and transaction.input != MINING_REWARD_INPUT:
            sender = transaction.input["address"]
            try:
                balance = Wallet.calculate_balance(self.blockchain, sender)
            except Exception:
                balance = None
            if balance is not None:
                def _net_spend(tx):
                    # Coins leaving the sender = input amount minus any change back to sender.
                    spend = tx.input.get("amount", 0)
                    change_back = tx.output.get(sender, 0)
                    return max(0, spend - change_back)

                pending_spend = sum(
                    _net_spend(tx)
                    for tx in self.transaction_map.values()
                    if tx.input.get("address") == sender
                )
                new_spend = _net_spend(transaction)
                if pending_spend + new_spend > balance:
                    raise Exception("Amount exceeds current on-chain balance")

        self.transaction_map[transaction.id] = transaction

    def existing_transaction(self, address):
        for transaction in self.transaction_map.values():
            if transaction.input["address"] == address:
                return transaction

    def transaction_data(self):
        return list(map(lambda transaction: transaction.to_json(), self.transaction_map.values()))

    def prioritized_transactions(self, limit=None):
        """
        Return transactions sorted by fee-per-byte descending.
        """
        txs = list(self.transaction_map.values())
        txs.sort(
            key=lambda tx: (
                tx.input.get("fee", 0) / max(1, len(json.dumps(tx.to_json()).encode("utf-8")))
            ),
            reverse=True
        )
        if limit:
            txs = txs[:limit]
        return txs

    def clear_blockchain_transactions(self, blockchain):
        for block in blockchain.chain:
            for transaction in block.data:
                try:
                    del self.transaction_map[transaction["id"]]
                except KeyError:
                    pass
