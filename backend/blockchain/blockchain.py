from backend.blockchain.block import Block
from backend.wallet.transaction import Transaction
from backend.config import MINING_REWARD_INPUT, MAX_TXS_PER_BLOCK, HALVING_INTERVAL, SUPPLY_MODEL, STARTING_REWARD
from backend.wallet.wallet import Wallet
from backend.economics import block_reward


class Blockchain:
    def __init__(self):
        self.chain = [Block.genesis()]

    def add_block(self, data):
        self.chain.append(Block.mine_block(self.chain[-1], data))

    def __repr__(self):
        return f'Blockchain: {self.chain}'

    def replace_chain(self, chain):
        """
        Replace the local chain if the incoming chain is longer and valid.
        """
        incoming_work = Blockchain.compute_work(chain)
        local_work = Blockchain.compute_work(self.chain)

        if len(chain) < len(self.chain):
            raise Exception('Cannot replace. The incoming chain must be longer.')

        if len(chain) == len(self.chain) and incoming_work <= local_work:
            raise Exception('Cannot replace. Incoming chain has no more work.')

        try:
            Blockchain.is_valid_chain(chain)
        except Exception as e:
            raise Exception(f'Cannot replace. The incoming chain is invalid: {e}')

        self.chain = chain

    def to_json(self):
        """
        Serialize the blockchain into a list of blocks.
        """
        return list(map(lambda block: block.to_json(), self.chain))

    def total_work(self) -> int:
        """
        Sum of work across the chain, used for fork choice.
        """
        return Blockchain.compute_work(self.chain)

    @staticmethod
    def from_json(chain_json):
        blockchain = Blockchain()
        blockchain.chain = list(
            map(lambda block_json: Block.from_json(block_json), chain_json)
        )
        return blockchain

    @staticmethod
    def is_valid_chain(chain):
        """
        Validate the entire chain:
        - Must start with the genesis block.
        - Each block must be valid and linked.
        """
        if chain[0] != Block.genesis():
            raise Exception('The genesis block must be valid')

        for i in range(1, len(chain)):
            block = chain[i]
            last_block = chain[i - 1]
            Block.is_valid_block(last_block, block)

        Blockchain.is_valid_transaction_chain(chain)

    @staticmethod
    def is_valid_transaction_chain(chain):
        transactions_ids = set()
        policy = Blockchain._policy_from_genesis(chain[0])

        for i in range(len(chain)):
            if i == 0:
                continue

            block = chain[i]
            has_mining_reward = False
            block_fee_total = 0
            reward_output_values = None
            in_block_balances = {}

            for transaction_json in block.data:
                transaction = Transaction.from_json(transaction_json)

                if transaction.id in transactions_ids:
                    raise Exception(f"Transaction: {transaction.id} is not unique")

                transactions_ids.add(transaction.id)

                if transaction.input == MINING_REWARD_INPUT:
                    if has_mining_reward:
                        raise Exception(
                            "There can only be one mining reward per block. "
                            f"Check block with hash: {block.hash}"
                        )
                    has_mining_reward = True
                    reward_output_values = list(transaction.output.values())
                elif transaction.input.get("type") == "GENESIS":
                    continue
                else:
                    historic_blockchain = Blockchain()
                    historic_blockchain.chain = chain[0:i]

                    sender_address = transaction.input["address"]
                    historic_balance = Wallet.calculate_balance(
                        historic_blockchain,
                        sender_address
                    )
                    available_balance = historic_balance + in_block_balances.get(sender_address, 0)
                    if transaction.input["amount"] > available_balance:
                        raise Exception(f"Transaction {transaction.id} has an invalid input amount")

                    block_fee_total += transaction.input.get("fee", 0)

                Transaction.is_valid_transaction(transaction)
                # Apply in-block balance deltas so subsequent txs in the same block see updated balances.
                if transaction.input not in (MINING_REWARD_INPUT, ) and transaction.input.get("type") != "GENESIS":
                    sender_address = transaction.input["address"]
                    spend_amount = transaction.input["amount"]
                    in_block_balances[sender_address] = in_block_balances.get(sender_address, 0) - spend_amount
                    for out_addr, out_value in transaction.output.items():
                        in_block_balances[out_addr] = in_block_balances.get(out_addr, 0) + out_value

            if not has_mining_reward:
                raise Exception(f"Missing mining reward at height {i}")

            if policy["start_reward"] is None and has_mining_reward and i == 1:
                inferred = reward_output_values and sum(reward_output_values) - block_fee_total
                policy["start_reward"] = inferred if inferred is not None else STARTING_REWARD

            expected_reward = block_reward(
                i,
                start_reward=policy["start_reward"] if policy["start_reward"] is not None else STARTING_REWARD,
                halving_interval=policy["halving_interval"],
                supply_model=policy["supply_model"],
            ) + block_fee_total
            reward_output_total = sum(reward_output_values or [])
            if reward_output_total != expected_reward:
                raise Exception(
                    f"Mining reward incorrect at height {i}: "
                    f"expected {expected_reward}, got {reward_output_total}"
                )

    @staticmethod
    def compute_work(chain) -> int:
        """
        Compute cumulative work as sum(2 ** difficulty) to reflect PoW effort.
        """
        return sum(2 ** max(0, block.difficulty) for block in chain)

    @staticmethod
    def _policy_from_genesis(genesis_block: Block):
        """
        Extract monetary policy from genesis block input to keep nodes with different configs in sync.
        """
        try:
            genesis_tx = genesis_block.data[0]
            g_input = genesis_tx.get("input", {}) if isinstance(genesis_tx, dict) else {}
        except Exception:
            g_input = {}
        return {
            "start_reward": g_input.get("start_reward"),
            "halving_interval": g_input.get("halving_interval") or HALVING_INTERVAL,
            "supply_model": g_input.get("supply_model") or SUPPLY_MODEL,
        }

    def policy(self):
        return self._policy_from_genesis(self.chain[0])


if __name__ == '__main__':
    blockchain = Blockchain()
    blockchain.add_block("one")
    blockchain.add_block("two")
    blockchain.add_block("three")

    print(blockchain)
