from backend.wallet.wallet import Wallet
from backend.blockchain.blockchain import Blockchain
from backend.wallet.transaction import Transaction
from backend.economics import block_reward


def test_verify_valid_signature():
    data = { "tx": "data"}
    wallet = Wallet()
    signature = wallet.sign(data)

    assert Wallet.verify(wallet.public_key, data, signature)

def test_verify_invalid_signature():
    data = { "tx": "data"}
    wallet = Wallet()
    signature = wallet.sign(data)

    assert not Wallet.verify(Wallet().public_key, data, signature)

def test_calculate_balance():
    blockchain = Blockchain()
    miner = Wallet(blockchain)
    wallet = Wallet(blockchain)

    # Fund miner
    blockchain.add_block([Transaction.reward_transaction(miner, block_reward(1)).to_json()])

    # Miner pays wallet
    incoming_amount = block_reward(1) // 2
    pay_tx = Transaction(miner, wallet.address, incoming_amount)
    pay_fee = pay_tx.input["fee"]
    blockchain.add_block([
        pay_tx.to_json(),
        Transaction.reward_transaction(miner, block_reward(2) + pay_fee).to_json()
    ])

    assert Wallet.calculate_balance(blockchain, wallet.address) == incoming_amount

    # Wallet spends
    spend_amount = 10
    spend_tx = Transaction(wallet, "recipient", spend_amount)
    spend_fee = spend_tx.input["fee"]
    blockchain.add_block([
        spend_tx.to_json(),
        Transaction.reward_transaction(miner, block_reward(3) + spend_fee).to_json()
    ])

    # Wallet receives again from miner
    received_amount = 15
    receive_tx = Transaction(miner, wallet.address, received_amount)
    fee_2 = receive_tx.input["fee"]
    blockchain.add_block([
        receive_tx.to_json(),
        Transaction.reward_transaction(miner, block_reward(4) + fee_2).to_json()
    ])

    expected_balance = incoming_amount - spend_amount - spend_fee + received_amount
    assert Wallet.calculate_balance(blockchain, wallet.address) == expected_balance
