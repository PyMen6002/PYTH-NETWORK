def hex_to_binary(hex_string: str) -> str:
    """
    Convert a hex string to its binary representation.
    """
    scale = 16  # hex base
    num_of_bits = len(hex_string) * 4
    return bin(int(hex_string, scale))[2:].zfill(num_of_bits)
