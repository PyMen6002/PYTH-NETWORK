from pubnub.pubnub import PubNub
from pubnub.pnconfiguration import PNConfiguration
from pubnub.callbacks import SubscribeCallback
import time
from backend.blockchain.block import Block
from backend.wallet.transaction import Transaction

pnconfig = PNConfiguration()
pnconfig.subscribe_key = "sub-c-f9f2aa1e-182e-4b1d-871d-d529e9869b5b"
pnconfig.publish_key = "pub-c-e61cdac0-e521-435b-ab78-53cc47939161"
pubnub = PubNub(pnconfig)

CHANNELS = {
    'TEST': 'TEST',
    'BLOCK': 'BLOCK',
    'TRANSACTION': 'TRANSACTION',
}

class Listener(SubscribeCallback):
    def __init__(self, blockchain, transaction_pool):
        self.blockchain = blockchain
        self.transaction_pool = transaction_pool

    def message(self, pubnub, message_object):
        print(f'\n-- Channel: {message_object.channel} | Message: {message_object.message}')
        
        if message_object.channel == CHANNELS['BLOCK']:
            block = Block.from_json(message_object.message)
            potential_chain = self.blockchain.chain[:]
            potential_chain.append(block)

            try:
                self.blockchain.replace_chain(potential_chain)
                self.transaction_pool.clear_blockchain_transactions(
                    self.blockchain
                )
                print(f'\n -- Succesfully replaced the local chain')
            except Exception as e:
                print(f'\n -- Did not replace chain: {e}')
        elif message_object.channel == CHANNELS['TRANSACTION']:
            transaction = Transaction.from_json(message_object.message)
            self.transaction_pool.set_transaction(transaction)
            print("\n -- Set the new transaction in the transaction pool")
        

class PubSub():
    def __init__(self, blockchain, transaction_pool):
        self.pubnub = PubNub(pnconfig)
        self.pubnub.subscribe().channels(CHANNELS.values()).execute()
        self.pubnub.add_listener(Listener(blockchain, transaction_pool))

    def publish(self, channel, message):
        self.pubnub.unsubscribe().channels([channel]).execute()
        self.pubnub.publish().channel(channel).message(message).sync()
        self.pubnub.subscribe().channels([channel]).execute()

    def broadcast_block(self, block):
        self.publish(CHANNELS['BLOCK'], block.to_json())

    def broadcast_transaction(self, transaction):
        self.publish(CHANNELS['TRANSACTION'], transaction.to_json())


if __name__ == '__main__':
    pubsub = PubSub()
    time.sleep(1)
    pubsub.publish(CHANNELS['TEST'], {'foo':'bar'})