from backend.wallet.transaction_pool import TransactionPool
from backend.wallet.transaction import Transaction
from backend.wallet.wallet import Wallet
from backend.blockchain.blockchain import Blockchain
from backend.economics import block_reward


def test_set_transaction():
    blockchain = Blockchain()
    miner = Wallet(blockchain)
    wallet = Wallet(blockchain)
    blockchain.add_block([Transaction.reward_transaction(miner, block_reward(len(blockchain.chain))).to_json()])
    funding_tx = Transaction(miner, wallet.address, 1000)
    funding_fee = funding_tx.input["fee"]
    blockchain.add_block([
        funding_tx.to_json(),
        Transaction.reward_transaction(miner, block_reward(len(blockchain.chain)) + funding_fee).to_json()
    ])

    transaction_pool = TransactionPool(blockchain)
    transaction = Transaction(wallet, 'recipient', 1)
    transaction_pool.set_transaction(transaction)

    assert transaction_pool.transaction_map[transaction.id] == transaction

def test_clear_blockchain_transactions():
    blockchain = Blockchain()
    miner = Wallet(blockchain)
    wallet = Wallet(blockchain)
    blockchain.add_block([Transaction.reward_transaction(miner, block_reward(len(blockchain.chain))).to_json()])
    funding_tx = Transaction(miner, wallet.address, 1000)
    funding_fee = funding_tx.input["fee"]
    blockchain.add_block([
        funding_tx.to_json(),
        Transaction.reward_transaction(miner, block_reward(len(blockchain.chain)) + funding_fee).to_json()
    ])
    transaction_pool = TransactionPool(blockchain)
    tx1 = Transaction(wallet, 'recipient', 12)
    tx2 = Transaction(wallet, 'recipient', 45)

    transaction_pool.set_transaction(tx1)
    transaction_pool.set_transaction(tx2)

    blockchain.add_block([tx1.to_json(), tx2.to_json()])

    assert tx1.id in transaction_pool.transaction_map
    assert tx2.id in transaction_pool.transaction_map

    transaction_pool.clear_blockchain_transactions(blockchain)

    assert not tx1.id in transaction_pool.transaction_map
    assert not tx2.id in transaction_pool.transaction_map
