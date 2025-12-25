import hashlib
import uuid
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    encode_dss_signature,
    decode_dss_signature
)
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature


class Wallet:
    def __init__(self, blockchain=None, private_key=None):
        self.blockchain = blockchain
        # Use a long, deterministic address from public key hash (like ETH-style hex)
        self.address = None
        if private_key:
            self.private_key = private_key
        else:
            self.private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        self.public_key_obj = self.private_key.public_key()
        self.public_key = self.public_key_hex()
        self.address = self.derive_address()

    @property
    def balance(self):
        return Wallet.calculate_balance(self.blockchain, self.address)

    def sign(self, data):
        return decode_dss_signature(
            self.private_key.sign(
                json.dumps(data).encode('utf-8'),
                ec.ECDSA(hashes.SHA256())
            ))

    def public_key_hex(self):
        bytes_uncompressed = self.public_key_obj.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        return bytes_uncompressed.hex()

    def derive_address(self):
        # Hash the PEM-encoded public key and take 40 hex chars (ETH-like length)
        digest = hashlib.sha256(bytes.fromhex(self.public_key)).hexdigest()
        return digest[:40]

    @classmethod
    def from_private_key(cls, private_key_hex: str, blockchain=None):
        errors = []
        private_key = None
        key_str = private_key_hex if isinstance(private_key_hex, str) else private_key_hex.decode()
        # Try PEM first
        try:
            private_key = serialization.load_pem_private_key(
                key_str.encode("utf-8"),
                password=None,
                backend=default_backend()
            )
        except Exception as exc:
            errors.append(exc)

        if private_key is None:
            try:
                int_key = int(key_str.strip(), 16)
                private_key = ec.derive_private_key(int_key, ec.SECP256K1(), default_backend())
            except Exception as exc:
                errors.append(exc)

        if private_key is None:
            last_error = errors[-1] if errors else "unknown error"
            raise Exception(f"Invalid private key: {last_error}")
        wallet = cls(blockchain=blockchain, private_key=private_key)
        return wallet

    @staticmethod
    def verify(public_key, data, signature):
        # public_key is hex string (uncompressed)
        public_bytes = bytes.fromhex(public_key)
        deserialized_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(),
            public_bytes
        )

        (r, s) = signature

        try:
            deserialized_public_key.verify(
                encode_dss_signature(r, s),
                json.dumps(data).encode('utf-8'),
                ec.ECDSA(hashes.SHA256())
            )

            return True
        except InvalidSignature:
            return False

    @staticmethod
    def calculate_balance(blockchain, address):
        """
        Compute balance by summing all outputs to the address and subtracting all spends from the address.
        """
        if not blockchain:
            return 0

        balance = 0
        for block in blockchain.chain:
            for transaction in block.data:
                tx_input = transaction.get("input", {})
                tx_output = transaction.get("output", {})

                # Subtract full spend (amount includes fee) when this address is the sender.
                if tx_input.get("address") == address:
                    balance -= tx_input.get("amount", 0)

                # Add any outputs to this address (includes change or rewards).
                if address in tx_output:
                    balance += tx_output[address]

        return balance


if __name__ == '__main__':
    wallet = Wallet()
    print(f'Wallet: {wallet.__dict__}')

    data = {'tx': 'addr'}
    signature = wallet.sign(data)
    print(f'sign: {signature}')

    should_valid = Wallet.verify(wallet.public_key, data, signature)
    print(f'Should Valid: {should_valid}')

    should_invalid = Wallet.verify(Wallet().public_key, data, signature)
    print(f'Should Invalid: {should_invalid}')
