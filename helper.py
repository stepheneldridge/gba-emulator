# #Big Endian
# def get_bytes(ram, start, length):
#     value = 0
#     for i in range(length):
#         value <<= 8
#         value += ram[start + i]
#     return value

# def set_bytes(ram, start, length, value):
#     temp = value
#     for i in range(length - 1, -1, -1):
#         ram[start + i] = value & 255
#         value >>= 8

# Little Endian
def get_bytes(ram, start, length):
    value = 0
    for i in range(length):
        value <<= 8
        value += ram[start + length - 1 - i]
    return value


def set_bytes(ram, start, length, value):
    for i in range(length):
        ram[start + i] = value & 255
        value >>= 8


def UInt32(s):
    if s < 0:
        return s + (1 << 32)
    return s


def SInt32(s):
    if s & 1 << 31:
        return s - (1 << 32)
    return s


def Not32(s):
    return s ^ 0xffffffff


class Labeled32(object):
    def __init__(self, labels):
        # (name, bit, 1/0)
        self.value = 0
        for i in labels:
            setattr(self, i[0], i[1])
            setattr(self, i[0], i[2])

    def __getattribute__(self, name):
        i = object.__getattribute__(self, name)
        if name == "value":
            return i
        if callable(i):
            return i
        return 1 if self.value & 1 << i != 0 else 0

    def __setattr__(self, name, value):
        if not hasattr(self, name) or name == "value":
            object.__setattr__(self, name, value)
            return
        i = object.__getattribute__(self, name)
        if value:
            self.value |= 1 << i
        else:
            self.value &= Not32(1 << i)

    def set_bits(self, bit_list):
        for i in bit_list:
            self.value |= 1 << i


def format_hex(value, size):
    return "{0:#0{1}x}".format(value, 2 + size * 2)


def format_bin(value, size):
    out = bin(value)[2:]
    pad = size * 8 - len(out)
    out = "0" * pad + out
    return " ".join([out[::-1][i:i + 4][::-1] for i in range(0, len(out), 4)][::-1])
