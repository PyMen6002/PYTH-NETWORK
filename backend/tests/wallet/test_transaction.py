from backend.wallet.transaction import Transaction
from backend.wallet.wallet import Wallet
import pytest
from backend.config import MINING_REWARD, MINING_REWARD_INPUT

def test_transaction():
    sender_wallet = Wallet()
    recipient = 'recipient'
    amount = 50
    transaction = Transaction(sender_wallet, recipient, amount)

    assert transaction.output[recipient] == amount
    assert transaction.output[sender_wallet.address] == sender_wallet.balance - amount

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
    sender_wallet = Wallet()
    transaction = Transaction(sender_wallet, 'recipient', 50)
    with pytest.raises(Exception, match="Amount exceeds balance"):
        transaction.update(sender_wallet, 'recipient', 25000)

def test_transaction_update():
    sender_wallet = Wallet()
    firt_recipient = 'f1_recipient'
    first_amount = 50

    tx = Transaction(sender_wallet, firt_recipient, first_amount)

    next_recipient = 'n_recipient'
    next_amount = 75

    tx.update(sender_wallet, next_recipient, next_amount)

    assert tx.output[next_recipient] == next_amount
    assert tx.output[sender_wallet.address] == sender_wallet.balance - first_amount - next_amount

    assert Wallet.verify(
        tx.input["public_key"],
        tx.output,
        tx.input["signature"],
    )

    to_first_again_amount = 25
    tx.update(sender_wallet, firt_recipient, to_first_again_amount)

    assert tx.output[firt_recipient] == first_amount + to_first_again_amount
    assert tx.output[sender_wallet.address] == sender_wallet.balance - first_amount - next_amount - to_first_again_amount

    assert Wallet.verify(
        tx.input["public_key"],
        tx.output,
        tx.input["signature"],
    )


def test_valid_transaction():
    Transaction.is_valid_transaction(Transaction(Wallet(), "recipient", 50))

def test_valid_transaction_with_invalid_outputs():
    sender_wallet = Wallet()
    transaction = Transaction(sender_wallet, "recipient", 50)
    transaction.output[sender_wallet.address] = 25000

    with pytest.raises(Exception, match="Invalid transaction output values"):
        Transaction.is_valid_transaction(transaction)

def test_valid_transaction_with_invalid_signature():
    transaction = Transaction(Wallet(), "recipient", 50)
    transaction.input["signature"] = Wallet().sign(transaction.output)

    with pytest.raises(Exception, match="Invalid signature"):
        Transaction.is_valid_transaction(transaction)

def test_reward_transaction():
    miner_wallet = Wallet()
    tx = Transaction.reward_transaction(miner_wallet)

    assert tx.input == MINING_REWARD_INPUT
    assert tx.output[miner_wallet.address] == MINING_REWARD

def test_valid_reward_transaction():
    reward_transaction = Transaction.reward_transaction(Wallet())
    Transaction.is_valid_transaction(reward_transaction)

def test_invalid_reward_transaction_extra_recipient():
    reward_transaction = Transaction.reward_transaction(Wallet())
    reward_transaction.output["extra_recipient"] = 60

    with pytest.raises(Exception, match="Invalid mining reward"):
        Transaction.is_valid_transaction(reward_transaction)

def test_invalid_reward_transaction_invalid_amount():
    miner_wallet = Wallet()
    reward_transaction = Transaction.reward_transaction(miner_wallet)
    reward_transaction.output[miner_wallet.address] = 1200

    with pytest.raises(Exception, match="Invalid mining reward"):
        Transaction.is_valid_transaction(reward_transaction)