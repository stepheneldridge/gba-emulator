import sys
import getopt
from os import environ
from processor import Processor
from helper import *

environ["PYGAME_HIDE_SUPPORT_PROMPT"] = 'TRUE'
import pygame
from pygame.locals import *

# Graphics
class Graphics:
    def __init__(self, w, h, vram, sx, sy):
        self.width = w
        self.height = h
        self.vram = vram
        self.scale = (sx, sy)
        self.display = pygame.display.set_mode((self.width * sx, self.height * sy))
        self.color_map = [i * 255 // 31 for i in range(32)]
        self.word_size = self.vram.word_size

    def rgb15(self, r, g, b):
        return r | (g << 5) | (b << 10)

    def get_rgb15(self, v):
        return self.color_map[v & 31], self.color_map[(v >> 5) & 31], self.color_map[(v >> 10) & 31]

    def mode3_render(self):
        for i in range(self.width):
            for j in range(self.height):
                color = self.get_rgb15(get_bytes(self.vram.data, (i + j * self.width) * self.word_size, 2))
                pygame.draw.rect(self.display, color, (i * self.scale[0], j * self.scale[1], self.scale[0], self.scale[1]))

    def mode3_write(self, x, y, v):
        set_bytes(self.vram.data, (x + y * self.width) * self.word_size, 2, v)


# IO
class InputOutput:
    def __init__(self, io_ram):
        self.io_ram = io_ram

    def set_video_mode(m):
        assert m < 6
        self.io_ram.data[0] &= 0b11111000
        self.io_ram.data[0] |= m
        self.DCNT_MODE = m

    @property
    def DCNT_GB(self):
        return self.io_ram.data[0] & 8

    @property
    def DCNT_PAGE(self):
        return self.io_ram.data[0] & 16

    @property
    def DCNT_OAM_HBL(self):
        return self.io_ram.data[0] & 32

    @property
    def DCNT_OBJ_1D(self):
        return self.io_ram.data[0] & 64

    @property
    def DCNT_BLANK(self):
        return self.io_ram.data[0] & 128

    @property
    def DCNT_LAYER(self):
        return self.io_ram.data[1] & 0b11111

    @property
    def DCNT_WIN(self):
        return self.io_ram.data[1] & (0b111 << 5)


# Memory
class MemoryBank:
    def __init__(self, start, end, port_size, zero=False):
        self.start = start
        self.end = end
        self.port_size = port_size
        self.word_size = port_size // 8
        self.data = []
        if(zero):
            for i in range(start, end):
                self.data.append(0)

    def initialize(self, data):
        self.data = data

    def inside(self, x):
        return x <= self.end and x >= self.start

    def get(self, x):
        if(self.inside(x)):
            return self.data[x]
        else:
            raise Exception("Memory out of bounds: %s" % x)

    def set(self, x, v):
        if(self.inside(x)):
            self.data[x] = v
        else:
            raise Exception("Memory out of bounds: %s" % x)


class Memory:
    def __init__(self):
        self.SYS_ROM = MemoryBank(0x00000000, 0x00003fff, 32)
        self.EWRAM = MemoryBank(0x02000000, 0x0203ffff, 16, zero=True)
        self.IWRAM = MemoryBank(0x03000000, 0x03007fff, 32, zero=True)
        self.IO_RAM = MemoryBank(0x04000000, 0x040003ff, 16, zero=True)
        self.PAL_RAM = MemoryBank(0x05000000, 0x050003ff, 16, zero=True)
        self.VRAM = MemoryBank(0x06000000, 0x06017fff, 16, zero=True)
        self.OAM = MemoryBank(0x07000000, 0x070003ff, 32)
        self.PAK_ROM = MemoryBank(0x08000000, 0x09ffffff, 16)
        self.CART_RAM = MemoryBank(0x0e000000, 0x0e00ffff, 8)  # 64kb
        self.total = [self.SYS_ROM, self.EWRAM, self.IWRAM, self.IO_RAM, self.PAL_RAM, self.VRAM, self.OAM, self.PAK_ROM, self.CART_RAM]

    def lookup(self, addr, length):
        for i in self.total:
            if i.inside(addr):
                return get_bytes(i.data, addr - i.start, length)
        raise Exception("Memory out of bounds: %s" % addr)

    def write_word(self, addr, value):
        return self.write_bytes(addr, value, 4)

    def write_byte(self, addr, value):
        return self.write_bytes(addr, value, 1)

    def write_bytes(self, addr, value, count):
        for i in self.total:
            if i.inside(addr):
                return set_bytes(i.data, addr - i.start, count, value)
        raise Exception("Memory out of bounds: %s" % addr)

def load_bios(mem, name):
    file = open(name, "rb")
    data = file.read()
    mem.SYS_ROM.initialize(data)


def load_rom(mem, name):
    file = open(name, "rb")
    data = file.read()
    mem.PAK_ROM.initialize(data)


def main(argv):
    bios = ""
    rom = ""
    debug = False
    try:
        opts, args = getopt.getopt(argv, "hvb:r:", ["bios=", "rom="])
    except getopt.GetoptError:
        print("gba.py -b <bios> -r <rom>")
        sys.exit()
    for opt, arg in opts:
        if opt == "-h":
            print("gba.py -b <bios> -r <rom>")
            sys.exit()
        elif opt in ("-b", "--bios"):
            bios = arg
        elif opt in ("-r", "--rom"):
            rom = arg
        elif opt == "-v":
            debug = True
    if bios == "":
        print("No bios provided")
        sys.exit()

    pygame.init()
    mem = Memory()
    gpu = Graphics(240, 160, mem.VRAM, 5, 5)
    fps = pygame.time.Clock()
    pygame.display.set_caption(rom or bios)
    cpu = Processor(mem, console_debug=debug)
    load_bios(mem, bios)
    if rom:
        load_rom(mem, rom)

    while True:
        # for event in pygame.event.get():
        #     if event.type == QUIT:
        #         pygame.quit()
        #         sys.exit()
        # gpu.mode3_render()
        # pygame.display.update()
        # fps.tick(60)
        cpu.step()

if __name__ == "__main__":
    main(sys.argv[1:])