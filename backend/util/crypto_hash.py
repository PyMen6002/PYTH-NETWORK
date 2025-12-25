import hashlib
import json


def crypto_hash(*args):
    """
    Return a sha-256 hash of the given arguments.
    Arguments are converted to JSON strings and sorted to ensure deterministic hashing.
    """
    stringified_args = sorted(map(lambda data: json.dumps(data, sort_keys=True), args))
    joined_data = "".join(stringified_args)
    return hashlib.sha256(joined_data.encode("utf-8")).hexdigest()


if __name__ == '__main__':
    print(f"Crypto: {crypto_hash('foo', 'two', 2)}")
    print(f"Crypto: {crypto_hash(2, 'two', 'foo')}")
