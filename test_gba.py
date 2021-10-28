import processor
import helper
import unittest
from unittest.mock import MagicMock

class Test_Labeled32(unittest.TestCase):
    def test_Labeled32(self):
        label = helper.Labeled32([("A", 0, 1), ("Z", 31, 1), ("something", 30, 0)])
        self.assertEqual(label.value, 0x80000001)
        label.A = 0
        self.assertEqual(label.value, 0x80000000)
        label.something = 1
        self.assertEqual(label.value, 0xc0000000)
        self.assertEqual(label.Z, 1)
        self.assertEqual(label.A, 0)

class Test_CPU(unittest.TestCase):
    def setUp(self):
        self.cpu = processor.Processor(0)

    def test_SignExtend(self):
        x = 0b0100
        self.assertEqual(self.cpu.SignExtend(x, 2, 4), x)  # extends with 0s
        y = 0b1100
        self.assertEqual(self.cpu.SignExtend(y, 2, 4), 0b111100)

    def test_ROR(self):
        v = self.cpu.ROR(1, 1)
        self.assertEqual(v, 1 << 31)
        v = self.cpu.ROR(3, 2)
        self.assertEqual(v, 3 << 30)
        v = self.cpu.ROR(0x7fffffff, 5)
        self.assertEqual(v, 0xfbffffff)
        v = self.cpu.ROR(0x2856abcd, 0)
        self.assertEqual(v, 0x2856abcd)
        v = self.cpu.ROR(0x2856abcd, 30)
        self.assertEqual(v, 0xa15aaf34)

    def test_LSL(self):
        v = self.cpu.LSL(1, 0)
        self.assertEqual(v, 1)
        v = self.cpu.LSL(0b00010001000100010001000100010001, 10)
        self.assertEqual(v, 0b01000100010001000100010000000000)
        self.cpu.write_flags = True
        self.assertFalse(self.cpu.C)
        v = self.cpu.LSL(0b10010001000100010001000100010001, 1)
        self.assertEqual(v, 0b00100010001000100010001000100010)
        self.assertTrue(self.cpu.C)
        v = self.cpu.LSL(0b10010001000100010001000100010001, 2)
        self.assertEqual(v, 0b01000100010001000100010001000100)
        self.assertFalse(self.cpu.C)

    def test_LSR(self):
        self.cpu.write_flags = True
        self.assertEqual(self.cpu.LSR(10, 2), 2)
        self.assertTrue(self.cpu.C)
        self.assertEqual(self.cpu.LSR(50, 4), 3)
        self.assertFalse(self.cpu.C)
        self.cpu.write_flags = False
        unchanged = self.cpu.C
        self.assertEqual(self.cpu.LSR(10, 2), 2)
        self.assertEqual(self.cpu.C, unchanged)
        self.assertEqual(self.cpu.LSR(50, 4), 3)
        self.assertEqual(self.cpu.C, unchanged)

    def test_ASR(self):
        self.cpu.write_flags = True
        self.assertEqual(self.cpu.ASR(0b10010001000100010001000100010001, 3), 0b11110010001000100010001000100010)
        self.assertEqual(self.cpu.ASR(10, 2), 2)
        self.assertTrue(self.cpu.C)
        self.assertEqual(self.cpu.ASR(50, 4), 3)
        self.assertFalse(self.cpu.C)
        self.cpu.write_flags = False
        unchanged = self.cpu.C
        self.assertEqual(self.cpu.ASR(10, 2), 2)
        self.assertEqual(self.cpu.C, unchanged)
        self.assertEqual(self.cpu.ASR(50, 4), 3)
        self.assertEqual(self.cpu.C, unchanged)

    def test_RRX(self):
        self.cpu.write_flags = True
        self.assertEqual(self.cpu.RRX(10, 0), 5)
        self.assertFalse(self.cpu.C)
        self.assertEqual(self.cpu.RRX(10, 1), 5 + (1 << 31))
        self.assertFalse(self.cpu.C)
        self.assertEqual(self.cpu.RRX(11, 0), 5)
        self.assertTrue(self.cpu.C)
        self.cpu.write_flags = False
        unchanged = self.cpu.C
        self.assertEqual(self.cpu.RRX(10, 0), 5)
        self.assertEqual(self.cpu.C, unchanged)
        self.assertEqual(self.cpu.RRX(10, 1), 5 + (1 << 31))
        self.assertEqual(self.cpu.C, unchanged)
        self.assertEqual(self.cpu.RRX(11, 0), 5)
        self.assertEqual(self.cpu.C, unchanged)

    def test_shift(self):
        rrx = MagicMock(return_value="RRX")
        self.cpu.RRX = rrx
        other = MagicMock(return_value="other")
        self.assertEqual(self.cpu.shift(37, other, 0, 1), 37)
        other.assert_not_called()
        self.assertEqual(self.cpu.shift(37, other, 2, 1), "other")
        other.assert_called_with(37, 2)
        self.assertEqual(self.cpu.shift(37, rrx, 3, 1), "RRX")
        rrx.assert_called_with(37, 1)


    def test_get_immediate(self):
        self.assertEqual(self.cpu.get_immediate(0x0bff), 261120)
        self.assertEqual(self.cpu.get_immediate(0x01d3), 3221225524)

    def test_CMP_immediate(self):
        # N Z C V
        self.cpu.reg[0] = self.cpu.get_immediate(0x047f)
        param = {
            "rn": 0,
            "im": 1,
            "rest": 0x04ff
        }
        self.cpu.CMP(param)
        self.assertEqual(self.cpu.status >> 28, 0x9) # N V

        param = {
            "rn": 0,
            "im": 1,
            "rest": 0x06ff
        }
        self.cpu.CMP(param)
        self.assertEqual(self.cpu.status >> 28, 0x2) # C

        param = {
            "rn": 0,
            "im": 1,
            "rest": 0x047f
        }
        self.cpu.CMP(param)
        self.assertEqual(self.cpu.status >> 28, 0x6) # Z C


        self.cpu.reg[0] = self.cpu.get_immediate(0x007f)

        param = {
            "rn": 0,
            "im": 1,
            "rest": 0x00ff
        }
        self.cpu.CMP(param)
        self.assertEqual(self.cpu.status >> 28, 0x8) # N

        self.cpu.reg[0] = self.cpu.get_immediate(0x0102)

        param = {
            "rn": 0,
            "im": 1,
            "rest": 0x047f
        }
        self.cpu.CMP(param)
        self.assertEqual(self.cpu.status >> 28, 0x3) # C V


if __name__ == "__main__":
    unittest.main()
