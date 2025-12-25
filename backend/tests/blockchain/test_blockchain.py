from backend.blockchain.blockchain import Blockchain
from backend.blockchain.block import GENESIS_DATA
import pytest
from backend.wallet.transaction import Transaction
from backend.wallet.wallet import Wallet
from backend.economics import block_reward

def test_blockchain_instance():
    blockchain = Blockchain()

    assert blockchain.chain[0].hash == GENESIS_DATA['hash']

def test_add_block():
    blockchain = Blockchain()
    data = 'test-data'
    blockchain.add_block(data)

    assert blockchain.chain[-1].data == data

@pytest.fixture
def blockchain_blocks():
    blockchain = Blockchain()
    miner = Wallet(blockchain)
    sender = Wallet(blockchain)

    # Fund miner
    blockchain.add_block([Transaction.reward_transaction(miner, block_reward(len(blockchain.chain))).to_json()])

    # Send a portion of the reward to the sender, leaving room for fees.
    fund_tx = Transaction(miner, sender.address, block_reward(1) // 2)
    fund_fee = fund_tx.input["fee"]
    blockchain.add_block([
        fund_tx.to_json(),
        Transaction.reward_transaction(miner, block_reward(len(blockchain.chain)) + fund_fee).to_json()
    ])

    for i in range(5):
        tx = Transaction(sender, 'recipient', i + 1)
        tx_fee = tx.input["fee"]
        blockchain.add_block([
            tx.to_json(),
            Transaction.reward_transaction(miner, block_reward(len(blockchain.chain)) + tx_fee).to_json()
        ])
    blockchain.test_sender = sender
    blockchain.test_miner = miner
    return blockchain

def test_is_valid_chain(blockchain_blocks):
    Blockchain.is_valid_chain(blockchain_blocks.chain)

def test_is_valid_chain_bad_genesis(blockchain_blocks):
    blockchain_blocks.chain[0].hash = 'evil_hash'
    
    with pytest.raises(Exception, match='genesis block must be valid'):
        Blockchain.is_valid_chain(blockchain_blocks.chain)

def test_replace_chain(blockchain_blocks):
    blockchain = Blockchain()
    blockchain.replace_chain(blockchain_blocks.chain)

    assert blockchain.chain == blockchain_blocks.chain

def test_replace_chain_not_longer(blockchain_blocks):
    blockchain = Blockchain()

    with pytest.raises(Exception, match='The incoming chain must be longer'):
        blockchain_blocks.replace_chain(blockchain.chain)

def test_replace_chain_bad_chain(blockchain_blocks):
    blockchain = Blockchain()
    blockchain_blocks.chain[1].hash = 'evil_hash'

    with pytest.raises(Exception, match="The incoming chain is invalid"):
        blockchain.replace_chain(blockchain_blocks.chain)

def test_valid_transaction_chain(blockchain_blocks):
    Blockchain.is_valid_transaction_chain(blockchain_blocks.chain)

def test_is_valid_transaction_chain_duplicate_transactions(blockchain_blocks):
    tx = Transaction(blockchain_blocks.test_sender, 'recipient', 1)
    tx_fee = tx.input["fee"]
    transaction = tx.to_json()
    blockchain_blocks.add_block([
        transaction,
        transaction,
        Transaction.reward_transaction(
            blockchain_blocks.test_miner,
            block_reward(len(blockchain_blocks.chain)) + (tx_fee * 2)
        ).to_json()
    ])

    with pytest.raises(Exception, match="is not unique"):
        Blockchain.is_valid_transaction_chain(blockchain_blocks.chain)

def test_is_valid_transaction_chain_same_block_double_spend(blockchain_blocks):
    sender = blockchain_blocks.test_sender
    miner = blockchain_blocks.test_miner

    tx1 = Transaction(sender, 'r1', 1)
    tx2 = Transaction(sender, 'r2', 2)
    combined_fees = tx1.input["fee"] + tx2.input["fee"]

    blockchain_blocks.add_block([
        tx1.to_json(),
        tx2.to_json(),
        Transaction.reward_transaction(
            miner,
            block_reward(len(blockchain_blocks.chain)) + combined_fees
        ).to_json()
    ])

    with pytest.raises(Exception, match="invalid input amount"):
        Blockchain.is_valid_transaction_chain(blockchain_blocks.chain)

def test_is_valid_transaction_chain_multiple_rewards(blockchain_blocks):
    reward_amount = block_reward(len(blockchain_blocks.chain))
    reward_1 = Transaction.reward_transaction(Wallet(), reward_amount).to_json()
    reward_2 = Transaction.reward_transaction(Wallet(), reward_amount).to_json()

    blockchain_blocks.add_block([reward_1, reward_2])

    with pytest.raises(Exception, match="one mining reward per block"):
        Blockchain.is_valid_transaction_chain(blockchain_blocks.chain)

def test_is_valid_transaction_chain_bad_transaction(blockchain_blocks):
    bad_transaction = Transaction(blockchain_blocks.test_sender, 'recipient', 1)
    bad_transaction.input["signature"] = Wallet().sign(bad_transaction.output)
    blockchain_blocks.add_block([
        bad_transaction.to_json(),
        Transaction.reward_transaction(
            blockchain_blocks.test_miner,
            block_reward(len(blockchain_blocks.chain)) + bad_transaction.input.get("fee", 0)
        ).to_json()
    ])

    with pytest.raises(Exception):
        Blockchain.is_valid_transaction_chain(blockchain_blocks.chain)

def test_is_valid_transaction_chain_bad_historic_balance(blockchain_blocks):
    wallet = blockchain_blocks.test_sender
    bad_transaction = Transaction(wallet, 'recipient', 1)
    bad_transaction.output[wallet.address] = 9000
    bad_transaction.input["amount"] = 9001
    bad_transaction.input["signature"] = wallet.sign(bad_transaction.output)

    blockchain_blocks.add_block([
        bad_transaction.to_json(),
        Transaction.reward_transaction(
            blockchain_blocks.test_miner,
            block_reward(len(blockchain_blocks.chain)) + bad_transaction.input.get("fee", 0)
        ).to_json()
    ])

    with pytest.raises(Exception, match="Invalid transaction output values"):
        Blockchain.is_valid_transaction_chain(blockchain_blocks.chain)
