from helper import *


class Processor:
    def __init__(self, mem, console_debug=False):
        if not console_debug:
            self.print = lambda *args, **kwargs: None
        self.fetch = 0
        self.decode = 0
        self.state = "ARM"  # or THUMB
        # thumb exceptions to go arm and revert after completion
        self.word_size = 4
        self.write_flags = False
        self.memory = mem
        self.ops = [

        ]
        self.cond = [
            lambda: self.Z,
            lambda: not self.Z,
            lambda: self.C,
            lambda: not self.C,
            lambda: self.N,
            lambda: not self.N,
            lambda: self.V,
            lambda: not self.V,
            lambda: self.C and not self.Z,
            lambda: not self.C and self.Z,
            lambda: self.N == self.V,
            lambda: self.N != self.V,
            lambda: not self.Z and self.N == self.V,
            lambda: self.Z and self.N != self.V,
            lambda: True,
            lambda: False
        ]
        self.ops0s = [
            self.AND,
            self.EOR,
            self.SUB,
            self.RSB,
            self.ADD,
            self.ADC,
            self.SBC,
            self.RSC,
            self.TST,
            self.TEQ,
            self.CMP,
            self.CMN,
            self.ORR,
            self.MOV,
            self.BIC,
            self.MVN
        ]
        self.ops0 = [
            self.AND,
            self.EOR,
            self.SUB,
            self.RSB,
            self.ADD,
            self.ADC,
            self.SBC,
            self.RSC,
            self.MRS,
            self.MSR,
            self.MRS,
            self.MSR,
            self.ORR,
            self.MOV,
            self.BIC,
            self.MVN
        ]
        self.t_ops = [
            self.AND,
            self.EOR,
            self.T_LSL,
            self.T_LSR,
            self.T_ASR,
            self.ADC,
            self.SBC,
            self.ROR,
            self.TST,
            self.T_NEG,
            self.CMP,
            self.CMN,
            self.ORR,
            self.T_MUL,
            self.BIC,
            self.MVN
        ]
        self.shift_codes = [
            self.LSL,
            self.LSR,
            self.ASR,
            self.ROR
        ]
        self.reg = [
            0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0
        ]
        self.status = 0
        self.saved_status = {
            0b10001: 0,
            0b10010: 0,
            0b10011: 0,
            0b10110: 0,
            0b10111: 0,
            0b11010: 0,
            0b11011: 0
        }
        self.PC = 0
        self.LR = 0
        self.SP = 0
        self.MODE_usr = 0b10000
        self.MODE_fiq = 0b10001
        self.MODE_irq = 0b10010
        self.MODE_svc = 0b10011
        self.MODE_mon = 0b10110
        self.MODE_abt = 0b10111
        self.MODE_hyp = 0b11010
        self.MODE_und = 0b11011
        self.MODE_sys = 0b11111
        self.ITSTATE = 0b00000000
        self.SCTLR = Labeled32(
            [("TE", 30, 1), ("AFE", 29, 0), ("TRE", 28, 0), ("NMFI", 27, 1), ("EE", 25, 1), ("VE", 24, 0),
             ("U", 22, 1), ("FI", 21, 0), ("UWXN", 20, 0), ("WXN", 19, 0), ("HA", 17, 0), ("RR", 14, 0),
             ("V", 13, 1), ("I", 12, 0), ("Z", 11, 0), ("SW", 10, 0), ("B", 7, 0), ("C15BEN", 5, 1),
             ("C", 2, 0), ("A", 1, 0), ("M", 0, 0)]
        )
        self.SCTLR.set_bits([23, 18, 16, 6, 4, 3])

    def print(self, *args, **kwargs):
        print(*args, **kwargs)

    @property
    def PC(self):
        return self.reg[15]

    @PC.setter
    def PC(self, v):
        self.reg[15] = UInt32(v) & (0xfffffffc if not self.T else 0xfffffffe)

    @property
    def LR(self):
        return self.reg[14]

    @LR.setter
    def LR(self, v):
        self.reg[14] = v

    @property
    def SP(self):
        return self.reg[13]

    @SP.setter
    def SP(self, v):
        self.reg[13] = v

    @property
    def N(self):
        return (self.status & (1 << 31)) != 0

    @N.setter
    def N(self, v):
        if v:
            self.status |= (1 << 31)
        else:
            self.status &= Not32(1 << 31)

    @property
    def Z(self):
        return (self.status & (1 << 30)) != 0

    @Z.setter
    def Z(self, v):
        if v:
            self.status |= (1 << 30)
        else:
            self.status &= Not32(1 << 30)

    @property
    def C(self):
        return (self.status & (1 << 29)) != 0

    @C.setter
    def C(self, v):
        if v:
            self.status |= (1 << 29)
        else:
            self.status &= Not32(1 << 29)

    @property
    def V(self):
        return (self.status & (1 << 28)) != 0

    @V.setter
    def V(self, v):
        if v:
            self.status |= (1 << 28)
        else:
            self.status &= Not32(1 << 28)

    @property
    def Q(self):
        return (self.status & (1 << 27)) != 0

    @Q.setter
    def Q(self, v):
        if v:
            self.status |= (1 << 27)
        else:
            self.status &= Not32(1 << 27)

    @property
    def T(self):
        return (self.status & (1 << 5)) != 0

    @T.setter
    def T(self, v):
        if v:
            self.status |= (1 << 5)
            self.state = "THUMB"
            self.word_size = 2
        else:
            self.status &= Not32(1 << 5)
            self.state = "ARM"
            self.word_size = 4

    def get_mode(self, s):
        return s & 0b11111

    def write_current_status(self, value, mask, is_return):
        # page 1153
        # security not included at this time
        priv = self.get_mode(self.status) != self.MODE_usr
        nmfi = self.SCTLR.NMFI
        copy = 0
        if mask & 8:
            copy |= 0xf8000000
            if is_return:
                copy |= 0x07000000
        if mask & 4:
            copy |= 0x000f0000
        if mask & 2:
            if is_return:
                copy |= 0x0000fc00
            copy |= 1 << 9
            if priv:  # and other stuff?
                copy |= 1 << 8
        if mask & 1:
            if priv:
                copy |= 1 << 7
            if priv and (not nmfi or not (value & 1 << 6)):
                copy |= 1 << 6
            if is_return:
                copy |= 1 << 5
            if priv:
                copy |= 0x1f
        self.status = (self.status & Not32(copy)) | (value & copy)

    def write_saved_status(self, value, mask):
        # not sys or usr
        copy = 0
        if mask & 8:
            copy |= 0xff000000
        if mask & 4:
            copy |= 0x000f0000
        if mask & 2:
            copy |= 0xff00
        if mask & 1:
            copy |= 0xff
        mode = self.get_mode(self.status)
        self.saved_status[mode] = (self.saved_status[mode] & Not32(copy)) | (value & copy)

    def step(self):
        # if self.decode != 0:
        #     print(format_hex(self.decode["bin"], self.word_size), format_bin(self.decode["bin"], self.word_size))
        #     self.decode["cmd"](self.decode)
        #     self.decode = 0
        # if self.fetch != 0:
        #     self.decode = self.decoder(self.fetch)
        #     self.fetch = 0
        # self.fetch = self.memory.lookup(self.PC, self.word_size)
        self.write_flags = False
        if self.decode != 0:
            if self.cond[self.decode["cond"]]():
                pc = self.PC
                self.decode["cmd"](self.decode)
                if self.PC != pc:
                    self.fetch = 0
            if True: #self.decode["cmd"] == self.NOP:
                self.print(self.decode["cmd"].__name__, self.cond[self.decode["cond"]]())
                self.print(format_hex(self.PC, self.word_size), format_bin(self.decode["bin"], self.word_size))
                self.print(self.reg)
                self.print("NZCV Q" + " " * 24 + "IFT4 3210")
                self.print(format_bin(self.status, 4))
                self.print()
            self.decode = 0
        if self.fetch != 0:
            self.decode = self.decoder(self.fetch)
            self.fetch = 0
        self.fetch = self.memory.lookup(self.PC, self.word_size)
        self.PC += self.word_size

    def decoder(self, cmd):
        decoded = {"cmd": self.NOP, "bin": cmd}
        if self.state == "THUMB":
            condition = 14
            if cmd & 1 << 15:
                pass
            else:
                if cmd & 1 << 14:
                    if cmd & 1 << 13:
                        pass
                    else:
                        if cmd & 1 << 12:
                            pass
                        else:
                            if cmd & 1 << 11:
                                pass
                            else:
                                if cmd & 1 << 10:
                                    pass
                                else:
                                    op = (cmd >> 6) & 15
                                    decoded["cmd"] = self.t_ops[op]
                                    decoded["rd"] = cmd & 7
                                    decoded["rm"] = (cmd >> 3) & 7
                else:
                    if cmd & 1 << 13:
                        pass
                    else:
                        decoded["rd"] = cmd & 7
                        if cmd & 1 << 12:
                            if cmd & 1 << 11:
                                pass
                            else:
                                decoded["rm"] = (cmd >> 3) & 7
                                decoded["im"] = True
                                decoded["immediate"] = (cmd >> 6) & 31
                                decoded["cmd"] = self.T_ASR

                        else:
                            decoded["rm"] = (cmd >> 3) & 7
                            decoded["im"] = True
                            decoded["immediate"] = (cmd >> 6) & 31
                            if cmd & 1 << 11:
                                decoded["cmd"] = self.T_LSR
                            else:
                                decoded["cmd"] = self.T_LSL  # 469
        else:
            condition = cmd >> 28
            # First 3 bits
            if cmd & 1 << 27:
                if cmd & 1 << 26:
                    if cmd & 1 << 25:  # 111
                        pass
                    else:  # 110
                        pass
                else:
                    if cmd & 1 << 25:  # 101
                        # branch
                        decoded["cmd"] = self.BRANCH
                        decoded["link"] = cmd & 1 << 24
                        # decoded["addr"] = (cmd & ((1 << 23) - 1)) - 1 + 2 # offset PC inc, offset fetch/decode
                        # decoded["neg"] = cmd & 1 << 23
                        decoded["addr"] = self.SignExtend(cmd & ((1 << 24) - 1), 8, 24)
                    else:  # 100
                        pass
            else:
                if cmd & 1 << 26:  # 01
                    im = cmd & 1 << 25 == 0
                    load = cmd & 1 << 20
                    decoded["im"] = im
                    decoded["rn"] = cmd >> 16 & 15
                    decoded["rd"] = cmd >> 12 & 15
                    decoded["rest"] = cmd & (1 << 12) - 1
                    decoded["priv"] = cmd & 1 << 24
                    decoded["U"] = cmd & 1 << 23
                    decoded["I"] = cmd & 1 << 22
                    decoded["W"] = cmd & 1 << 21
                    if load:
                        decoded["cmd"] = self.LDR
                    else:
                        decoded["cmd"] = self.STR
                else:
                    op = cmd >> 21 & 15
                    a = cmd & 1 << 7
                    b = cmd & 1 << 4
                    im = cmd & 1 << 25  # immediate mode
                    # shift = cmd >> 5 & 3
                    # ldr str on page 201
                    if a and b and not im:  # mul swp str ldr
                        t = cmd >> 5 & 3
                        if t != 0:  # extra ldr/str
                            decoded["rn"] = cmd >> 16 & 15
                            decoded["rd"] = cmd >> 12 & 15
                            top4 = cmd >> 4 & 0b11110000
                            decoded["rm"] = top4 + cmd & 15
                            decoded["priv"] = cmd & 1 << 24
                            decoded["U"] = cmd & 1 << 23
                            decoded["im"] = cmd & 1 << 22
                            decoded["W"] = cmd & 1 << 21
                            if cmd & (1 << 20):
                                if t == 1:
                                    decoded["cmd"] = self.LDRH
                                elif t == 2:
                                    decoded["cmd"] = self.LDRSB
                                elif t == 3:
                                    decoded["cmd"] = self.LDRSH
                            else:
                                decoded["cmd"] = self.STRH
                        else:  # misc
                            if op == 0:
                                decoded["cmd"] = self.MUL
                            elif op == 1:
                                decoded["cmd"] = self.MLA
                            elif op == 4:
                                decoded["cmd"] = self.UMULL
                            elif op == 5:
                                decoded["cmd"] = self.UMLAL
                            elif op == 6:
                                decoded["cmd"] = self.SMULL
                            elif op == 7:
                                decoded["cmd"] = self.SMLAL
                            else:
                                self.print("Invalid Misc op:", op, cmd)
                    else:
                        s = cmd & 1 << 20
                        if s:
                            decoded["cmd"] = self.ops0s[op]
                        else:
                            decoded["cmd"] = self.ops0[op]
                        decoded["im"] = im
                        decoded["rest"] = cmd & (1 << 12) - 1
                        if decoded["cmd"].__name__ == "MRS":
                            decoded["R"] = cmd & 1 << 22
                        elif decoded["cmd"].__name__ == "MSR":
                            if b:
                                decoded["cmd"] = self.BX
                                decoded["rm"] = cmd & 15
                            else:
                                decoded["field_mask"] = cmd >> 16 & 15
                                decoded["R"] = cmd & 1 << 22
                        else:
                            decoded["s"] = s
                            decoded["rn"] = cmd >> 16 & 15
                            decoded["rd"] = cmd >> 12 & 15
        decoded["cond"] = condition
        return decoded

    def get_reg_shift(self, rest):
        rm = rest & 15
        value = self.reg[rm]
        shift_code = (rest >> 5) & 3
        shift_t = self.shift_codes[shift_code]
        if rest & 16:  # shift by reg
            shift = self.reg[rest >> 8] & 255  # last byte only
            return self.shift(value, shift_t, shift, self.C)
        else:
            shift = rest >> 7
            if shift_code == 1:
                if shift == 0:
                    shift = 32
            elif shift_code == 2:
                if shift == 0:
                    shift = 32
            elif shift_code == 3:
                if shift == 0:
                    shift_t = self.RRX
                    shift = 1
            return self.shift(value, shift_t, shift, self.C)

    def shift(self, v, t, n, c):  # value type shift_count carry
        if n == 0:
            return v
        elif t is self.RRX:
            return t(v, c)
        else:
            return t(v, n)

    def get_immediate(self, rest):
        return self.ROR(rest & 255, rest >> 8 << 1)

    def SignExtend(self, a, i, N):  # num, how many to shift, length of a in bits
        first = a & 1 << N - 1
        if first != 0:
            return a + (((1 << i) - 1) << N)
        return a

    def ITAdvance(self):
        if (self.ITSTATE & 7) == 0:
            self.ITSTATE = 0
        else:
            self.ITSTATE = (self.ITSTATE & 0b11100000) | (((self.ITSTATE & 31) << 1) & 31)

    def InITBlock(self):
        return (self.ITSTATE & 15) != 0

    # THUMB Instructions
    def T_AND(self, param):
        self.write_flags = not self.InITBlock()
        r = self.reg[param["rd"]] & self.reg[param["rm"]]
        self.write_to_register(param, r)

    def T_LSL(self, param):
        self.write_flags = not self.InITBlock()
        shift = 0
        if param["im"]:
            shift = param["immediate"]
        else:
            shift = self.reg[param["rd"]] & 255
        value = self.shift(self.reg[param["rm"]], self.LSL, shift, self.C)
        param["s"] = self.write_flags
        self.write_to_register(param, value)

    def T_LSR(self, param):
        self.write_flags = not self.InITBlock()
        shift = 0
        if param["im"]:
            shift = param["immediate"]
        else:
            shift = self.reg[param["rd"]] & 255
        value = self.shift(self.reg[param["rm"]], self.LSR, shift, self.C)
        param["s"] = self.write_flags
        self.write_to_register(param, value)

    def T_ASR(self, param):
        self.write_flags = not self.InITBlock()
        shift = 0
        if param["im"]:
            shift = param["immediate"]
        else:
            shift = self.reg[param["rd"]] & 255
        value = self.shift(self.reg[param["rm"]], self.ASR, shift, self.C)
        param["s"] = self.write_flags
        self.write_to_register(param, value)

    def T_NEG(self, param):
        pass

    def T_MUL(self, param):
        pass

    def ROR(self, v, r):
        s = v >> r | (v & (1 << r) - 1) << 32 - r
        if self.write_flags and r != 0:
            self.C = s & 1 << 31
        return s

    def LSL(self, a, b):
        s = a << b
        if self.write_flags:
            self.C = s & 1 << 32
        return s & 0xffffffff

    def LSR(self, a, b):
        if self.write_flags:
            self.C = a & 1 << (b - 1)
        return a >> b

    def ASR(self, a, b):
        if self.write_flags:
            self.C = a & 1 << (b - 1)
        return self.SignExtend(a, b, 32) >> b

    def RRX(self, a, b):
        if self.write_flags:
            self.C = a & 1
        return (a + (b << 32)) >> 1

    def add_with_carry(self, x, y, i):
        us = UInt32(x) + UInt32(y) + i
        ss = SInt32(x) + SInt32(y) + i
        result = ss & 0xffffffff
        carry = UInt32(result) != us
        overflow = SInt32(result) != ss
        if self.write_flags:
            self.C = carry
            self.V = overflow
        return result

    def write_to_register(self, param, value):
        if param["rd"] == 15:
            # should not be allowed in hyp, user or system mode
            # page 1999
            self.write_current_status(self.saved_status[self.get_mode(self.status)], 0b1111, True)
            self.PC = value
        else:
            self.reg[param["rd"]] = value
            if param["s"]:
                self.N = value & 1 << 31
                self.Z = value == 0

    # ARM Instructions
    # logical instructions defined page 195
    def AND(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = v & value
        self.write_to_register(param, r)

    def EOR(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = v ^ value
        self.write_to_register(param, r)

    def SUB(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(v, Not32(value), 1)
        self.write_to_register(param, r)

    def RSB(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(Not32(v), value, 1)
        self.write_to_register(param, r)

    def ADD(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(v, value, 0)
        self.write_to_register(param, r)

    def ADC(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(v, value, self.C)
        self.write_to_register(param, r)

    def SBC(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(v, Not32(value), self.C)
        self.write_to_register(param, r)

    def RSC(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(Not32(v), value, self.C)
        self.write_to_register(param, r)

    def TST(self, param):
        self.write_flags = True
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = v & value
        self.N = r & 1 << 31
        self.Z = r == 0

    def TEQ(self, param):
        self.write_flags = True
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = v ^ value
        self.N = r & 1 << 31
        self.Z = r == 0

    def CMP(self, param):
        self.write_flags = True
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(v, Not32(value), 1)
        self.N = r & 1 << 31
        self.Z = r == 0

    def CMN(self, param):
        self.write_flags = True
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = self.add_with_carry(v, value, 0)
        self.N = r & 1 << 31
        self.Z = r == 0

    def ORR(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = v | value
        self.write_to_register(param, r)

    def MOV(self, param):  # see page 491 for rd=PC
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        self.write_to_register(param, value)

    def BIC(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        v = self.reg[param["rn"]]
        r = v & Not32(value)
        self.write_to_register(param, r)

    def MVN(self, param):
        self.write_flags = False if param["rd"] == 15 else param["s"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        self.write_to_register(param, Not32(value))

    def MRS(self, param):
        if param["R"]:
            self.reg[param["rd"]] = self.saved_status(self.get_mode(self.status))
        else:
            self.reg[param["rd"]] = self.status

    def MSR(self, param):
        m = param["field_mask"]
        value = 0
        if param["im"]:
            value = self.get_immediate(param["rest"])
        else:
            value = self.get_reg_shift(param["rest"])
        if param["R"]:
            self.write_saved_status(value, m)
        else:
            self.write_current_status(value, m, False)

    def LDR(self, param):
        offset = 0
        address = self.reg[param["rn"]]
        write_back = not param["priv"] or param["W"]
        if param["im"]:
            offset = param["rest"]
        else:
            offset = self.get_reg_shift(param["rest"])
        off_address = address
        if param["U"]:
            off_address += offset
        else:
            off_address -= offset

        if not param["priv"] and param["W"]:
            pass
        else:
            address = off_address if param["priv"] else address
        if param["rn"] == 15:
            address = off_address & 0xfffffffc
        data = 0
        if param["I"]:
            data = self.memory.lookup(address, 1)
        else:
            data = self.memory.lookup(address, self.word_size)
        if write_back and param["rn"] != 15:
            self.reg[param["rn"]] = off_address
        if param["rd"] == 15:
            self.PC = data
        else:
            self.reg[param["rd"]] = data

    def LDRH(self, param):
        write_back = not param["priv"] or param["W"]
        if param["im"]:
            offset = self.reg[param["rm"]]
        else:
            offset = self.shift(self.reg[param["rm"]], self.LSL, 0, self.C)
        if param["rn"] == 15:
            address = self.PC
        else:
            address = self.reg[param["rn"]]
        off_address = address
        if param["U"]:
            off_address += offset
        else:
            off_address -= offset
        address = off_address if param["priv"] else address
        data = self.memory.lookup(address, 2)
        if write_back and param["rn"] != 15:
            self.reg[param["rn"]] = off_address
        if param["rd"] == 15:
            self.PC = data
        else:
            self.reg[param["rd"]] = data


    def LDRSB(self, param):
        write_back = not param["priv"] or param["W"]
        if param["im"]:
            offset = self.reg[param["rm"]]
        else:
            offset = self.shift(self.reg[param["rm"]], self.LSL, 0, self.C)
        if param["rn"] == 15:
            address = self.PC
        else:
            address = self.reg[param["rn"]]
        off_address = address
        if param["U"]:
            off_address += offset
        else:
            off_address -= offset
        address = off_address if param["priv"] else address
        data = SignExtend(self.memory.lookup(address, 1), 8, 32)
        if write_back and param["rn"] != 15:
            self.reg[param["rn"]] = off_address
        if param["rd"] == 15:
            self.PC = data
        else:
            self.reg[param["rd"]] = data

    def LDRSH(self, param):
        write_back = not param["priv"] or param["W"]
        if param["im"]:
            offset = self.reg[param["rm"]]
        else:
            offset = self.shift(self.reg[param["rm"]], self.LSL, 0, self.C)
        if param["rn"] == 15:
            address = self.PC
        else:
            address = self.reg[param["rn"]]
        off_address = address
        if param["U"]:
            off_address += offset
        else:
            off_address -= offset
        address = off_address if param["priv"] else address
        data = SignExtend(self.memory.lookup(address, 2), 16, 32)
        if write_back and param["rn"] != 15:
            self.reg[param["rn"]] = off_address
        if param["rd"] == 15:
            self.PC = data
        else:
            self.reg[param["rd"]] = data

    def STR(self, param):
        # if rn = 13, priv, not U,W, rest=4 see PUSH
        # if not priv and W see STRT/STRBT
        offset = 0
        address = self.reg[param["rn"]]
        write_back = not param["priv"] or param["W"]
        if param["im"]:
            offset = param["rest"]
        else:
            offset = self.get_reg_shift(param["rest"])
        off_address = address
        if param["U"]:
            off_address += offset
        else:
            off_address -= offset

        if not param["priv"] and param["W"]:
            pass
        else:
            address = off_address if param["priv"] else address
        if param["I"]:
            self.memory.write_byte(address, param["rd"] & 0xff)
        else:
            self.memory.write_word(address, param["rd"])
        if write_back and param["rn"] != 15:
            self.reg[param["rn"]] = off_address

    def STRH(self, param):
        write_back = not param["priv"] or param["W"]
        if param["im"]:
            offset = param["rm"]
        else:
            offset = self.shift(self.reg[param["rm"]], self.LSL, 0, self.C)
        address = self.reg[param["rn"]]
        off_address = address
        if param["U"]:
            off_address += offset
        else:
            off_address -= offset
        address = off_address if param["priv"] else address
        self.memory.write_bytes(address, self.reg[param["rd"]], 2)
        if write_back and param["rn"] != 15:
            self.reg[param["rn"]] = off_address

    def MUL(self, param):
        pass

    def MLA(self, param):
        pass

    def UMULL(self, param):
        pass

    def UMLAL(self, param):
        pass

    def SMULL(self, param):
        pass

    def SMLAL(self, param):
        pass

    def NOP(self, param):
        pass

    def BRANCH(self, param):  # ignores last 2 bits, or 1 in thumb
        if param["link"]:
            self.LR = self.PC + self.word_size  # addr of next inst
        self.PC += (param["addr"] << 2)

    def BX(self, param):
        addr = self.reg[param["rm"]]
        if self.state == "ARM":
            if addr & 1:
                self.T = 1
            elif not (addr & 2):
                self.T = 0
        self.PC = addr