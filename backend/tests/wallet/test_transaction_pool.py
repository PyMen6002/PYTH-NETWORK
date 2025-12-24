from backend.wallet.transaction_pool import TransactionPool
from backend.wallet.transaction import Transaction
from backend.wallet.wallet import Wallet
from backend.blockchain.blockchain import Blockchain


def test_set_transaction():
    transaction_pool = TransactionPool()
    transaction = Transaction(Wallet(), 'recipient', 1)
    transaction_pool.set_transaction(transaction)

    assert transaction_pool.transaction_map[transaction.id] == transaction

def test_clear_blockchain_transactions():
    transaction_pool = TransactionPool()
    tx1 = Transaction(Wallet(), 'recipient', 12)
    tx2 = Transaction(Wallet(), 'recipient', 45)

    transaction_pool.set_transaction(tx1)
    transaction_pool.set_transaction(tx2)

    blockchain = Blockchain()
    blockchain.add_block([tx1.to_json(), tx2.to_json()])

    assert tx1.id in transaction_pool.transaction_map
    assert tx2.id in transaction_pool.transaction_map

    transaction_pool.clear_blockchain_transactions(blockchain)

    assert not tx1.id in transaction_pool.transaction_map
    assert not tx2.id in transaction_pool.transaction_map