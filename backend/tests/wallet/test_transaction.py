import pytest
from backend.wallet.transaction import Transaction
from backend.wallet.wallet import Wallet
from backend.blockchain.blockchain import Blockchain
from backend.config import MINING_REWARD_INPUT, MIN_ABSOLUTE_FEE
from backend.economics import block_reward


def funded_wallet(amount=50, fee=1):
    """
    Create a wallet funded via on-chain reward then transfer.
    """
    blockchain = Blockchain()
    miner_wallet = Wallet(blockchain)
    target_wallet = Wallet(blockchain)

    blockchain.add_block([Transaction.reward_transaction(miner_wallet, block_reward(1)).to_json()])

    reward_value = block_reward(1)
    target_fund = max(amount * 10, MIN_ABSOLUTE_FEE * 5)
    transfer_amount = min(target_fund, reward_value // 2)
    transfer_tx = Transaction(miner_wallet, target_wallet.address, transfer_amount)
    fee = transfer_tx.input["fee"]
    blockchain.add_block([
        transfer_tx.to_json(),
        Transaction.reward_transaction(miner_wallet, block_reward(2) + fee).to_json()
    ])

    return target_wallet, miner_wallet, blockchain, transfer_amount, fee

def test_transaction():
    sender_wallet, miner_wallet, blockchain, funded_amount, fee = funded_wallet()
    sender_wallet.blockchain = blockchain
    recipient = 'recipient'
    amount = max(1, funded_amount // 2)
    transaction = Transaction(sender_wallet, recipient, amount)

    assert transaction.output[recipient] == amount
    assert transaction.output[sender_wallet.address] == sender_wallet.balance - amount - transaction.input["fee"]

    assert "timestamp" in transaction.input
    assert transaction.input["amount"] == sender_wallet.balance
    assert transaction.input["address"] == sender_wallet.address
    assert transaction.input["public_key"] == sender_wallet.public_key

    assert Wallet.verify(
        transaction.input["public_key"],
        transaction.output,
        transaction.input["signature"],
    )

def test_transaction_exceeds_balance():
    with pytest.raises(Exception, match="Amount exceeds balance"):
        Transaction(Wallet(), 'recipient', 25000)

def test_transaction_update_exceeds_balance():
    sender_wallet, miner_wallet, blockchain, funded_amount, fee = funded_wallet()
    sender_wallet.blockchain = blockchain
    transaction = Transaction(sender_wallet, 'recipient', 20)
    with pytest.raises(Exception, match="Amount exceeds balance"):
        transaction.update(sender_wallet, 'recipient', sender_wallet.balance + 1)

def test_transaction_update():
    sender_wallet, miner_wallet, blockchain, funded_amount, fee = funded_wallet()
    sender_wallet.blockchain = blockchain
    firt_recipient = 'f1_recipient'
    first_amount = 20

    tx = Transaction(sender_wallet, firt_recipient, first_amount)

    next_recipient = 'n_recipient'
    next_amount = 10

    tx.update(sender_wallet, next_recipient, next_amount)

    assert tx.output[next_recipient] == next_amount
    assert tx.input["amount"] == sum(tx.output.values()) + tx.input["fee"]

    assert Wallet.verify(
        tx.input["public_key"],
        tx.output,
        tx.input["signature"],
    )

    to_first_again_amount = 25
    tx.update(sender_wallet, firt_recipient, to_first_again_amount)

    assert tx.output[firt_recipient] == first_amount + to_first_again_amount
    assert tx.input["amount"] == sum(tx.output.values()) + tx.input["fee"]

    assert Wallet.verify(
        tx.input["public_key"],
        tx.output,
        tx.input["signature"],
    )


def test_valid_transaction():
    sender_wallet, miner_wallet, blockchain, funded_amount, fee = funded_wallet()
    sender_wallet.blockchain = blockchain
    Transaction.is_valid_transaction(Transaction(sender_wallet, "recipient", 10))

def test_valid_transaction_with_invalid_outputs():
    sender_wallet, miner_wallet, blockchain, funded_amount, fee = funded_wallet()
    sender_wallet.blockchain = blockchain
    transaction = Transaction(sender_wallet, "recipient", 10)
    transaction.output[sender_wallet.address] = 25000

    with pytest.raises(Exception, match="Invalid transaction output values"):
        Transaction.is_valid_transaction(transaction)

def test_valid_transaction_with_invalid_signature():
    sender_wallet, miner_wallet, blockchain, funded_amount, fee = funded_wallet()
    sender_wallet.blockchain = blockchain
    transaction = Transaction(sender_wallet, "recipient", 10)
    transaction.input["signature"] = Wallet().sign(transaction.output)

    with pytest.raises(Exception, match="Invalid signature"):
        Transaction.is_valid_transaction(transaction)

def test_reward_transaction():
    miner_wallet = Wallet()
    reward_amount = block_reward(1)
    tx = Transaction.reward_transaction(miner_wallet, reward_amount)

    assert tx.input == MINING_REWARD_INPUT
    assert tx.output[miner_wallet.address] == reward_amount

def test_valid_reward_transaction():
    reward_transaction = Transaction.reward_transaction(Wallet(), block_reward(1))
    Transaction.is_valid_transaction(reward_transaction)

def test_reward_transaction_allows_split_outputs():
    reward_transaction = Transaction.reward_transaction(Wallet(), block_reward(1))
    reward_transaction.output["extra_recipient"] = 60

    # Transaction-level validation allows multiple reward outputs; chain validation enforces total value.
    Transaction.is_valid_transaction(reward_transaction)

def test_invalid_reward_transaction_invalid_amount():
    reward_transaction = Transaction.reward_transaction(Wallet(), 0)

    with pytest.raises(Exception, match="Invalid mining reward"):
        Transaction.is_valid_transaction(reward_transaction)
