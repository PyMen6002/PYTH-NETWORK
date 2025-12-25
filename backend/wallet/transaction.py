import uuid
import time
import json
import math
from backend.wallet.wallet import Wallet
from backend.config import (
    MINING_REWARD_INPUT,
    MIN_RELAY_FEE_PER_BYTE,
    MIN_ABSOLUTE_FEE,
    TX_SIZE_INPUT_OVERHEAD,
    DYNAMIC_FEE_BASE_PER_BYTE,
    FEE_CONGESTION_TARGET_TXS,
    FEE_MAX_MULTIPLIER,
)


class Transaction:
    def __init__(self, sender_wallet=None, recipient=None, amount=None, fee=None, id=None, output=None, input=None, mempool_size=0):
        self.id = id or str(uuid.uuid4())[0:8]
        if output:
            self.output = output
            final_fee = fee if fee is not None else input.get("fee", 0) if input else 0
        else:
            if amount is None:
                raise Exception("Amount is required")
            if amount <= 0:
                raise Exception("Amount must be positive")
            balance = sender_wallet.balance
            provisional_change = balance - amount
            if provisional_change < 0:
                raise Exception("Amount exceeds balance")

            provisional_output = {
                recipient: amount,
                sender_wallet.address: provisional_change
            }
            computed_fee = self.compute_fee(provisional_output, mempool_size=mempool_size)
            if amount + computed_fee > balance:
                raise Exception("Amount plus fee exceeds balance")

            change_after_fee = balance - amount - computed_fee
            self.output = {
                recipient: amount,
                sender_wallet.address: change_after_fee
            }
            final_fee = computed_fee

        self.input = input or self.create_input(sender_wallet, self.output, final_fee)

    def create_output(self, sender_wallet, recipient, amount, fee):
        if fee < 0:
            raise Exception('Fee cannot be negative')

        total_spend = amount + fee

        if total_spend > sender_wallet.balance:
            raise Exception('Amount plus fee exceeds balance')

        output = {}
        output[recipient] = amount
        output[sender_wallet.address] = sender_wallet.balance - total_spend

        return output
    
    def create_input(self, sender_wallet, output, fee):
        return {
            'timestamp': time.time_ns(),
            'amount': sum(output.values()) + fee,
            'address': sender_wallet.address,
            'public_key': sender_wallet.public_key,
            'signature': sender_wallet.sign(output),
            'fee': fee
        }

    def update(self, sender_wallet, recipient, amount, mempool_size=0):
        # Recompute fee based on new output
        if amount <= 0:
            raise Exception('Amount must be positive')

        current_change = self.output[sender_wallet.address]
        if amount > current_change:
            raise Exception('Amount exceeds balance')

        updated_output = dict(self.output)
        updated_output[recipient] = updated_output.get(recipient, 0) + amount
        updated_output[sender_wallet.address] = current_change - amount

        computed_fee = Transaction.compute_fee(updated_output, mempool_size=mempool_size)
        if computed_fee > updated_output[sender_wallet.address]:
            raise Exception('Amount exceeds balance after fee')

        updated_output[sender_wallet.address] -= computed_fee

        self.output = updated_output
        self.input = self.create_input(sender_wallet, self.output, computed_fee)

    def to_json(self):
        """
        Serialize the transaction.
        """
        return self.__dict__

    @staticmethod
    def from_json(transaction_json):
        return Transaction(**transaction_json)

    @staticmethod
    def is_valid_transaction(transaction):
        """
        Validate a transaction.
        """
        if transaction.input.get("type") == "GENESIS":
            return

        if transaction.input == MINING_REWARD_INPUT:
            values = list(transaction.output.values())
            if not values or any(v <= 0 for v in values):
                raise Exception("Invalid mining reward")
            return

        output_total = sum(transaction.output.values())

        fee = transaction.input.get("fee", 0)
        if fee < 0:
            raise Exception("Invalid fee")

        # Enforce relay fee per byte
        min_fee = Transaction.compute_fee(transaction.output)

        if fee < min_fee:
            raise Exception("Fee below minimum relay fee")

        if transaction.input["amount"] != output_total + fee:
            raise Exception("Invalid transaction output values")

        if not Wallet.verify(
            transaction.input["public_key"],
            transaction.output,
            transaction.input["signature"]
        ):
            raise Exception("Invalid signature")

    @staticmethod
    def reward_transaction(miner_wallet, reward_amount, override_address=None):
        output = {}
        target_address = override_address or miner_wallet.address
        output[target_address] = reward_amount

        return Transaction(input=MINING_REWARD_INPUT, output=output)

    @staticmethod
    def compute_fee(output, mempool_size=0):
        tx_size = len(json.dumps(output).encode("utf-8")) + TX_SIZE_INPUT_OVERHEAD
        congestion_multiplier = 1 + max(0, mempool_size) / max(1, FEE_CONGESTION_TARGET_TXS)
        congestion_multiplier = min(congestion_multiplier, FEE_MAX_MULTIPLIER)

        per_byte_fee = max(
            MIN_RELAY_FEE_PER_BYTE,
            DYNAMIC_FEE_BASE_PER_BYTE * congestion_multiplier
        )
        return int(max(per_byte_fee * tx_size, MIN_ABSOLUTE_FEE))


if __name__ == '__main__':
    tx = Transaction(Wallet(), 'recipient', 25)
    print(f'tx: {tx.__dict__}')

    transaction_json = tx.to_json()

    restored_tx = Transaction.from_json(transaction_json)
    print(f'tx: {restored_tx.__dict__}')
