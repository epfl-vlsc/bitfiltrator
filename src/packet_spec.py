# author: Sahand Kashani <sahand.kashani@epfl.ch>

import enum

import helpers

# Packet format: UG570 table 9-16 and 9-18
PACKET_HEADER_TYPE_IDX_HIGH = 31
PACKET_HEADER_TYPE_IDX_LOW = 29
PACKET_HEADER_TYPE_WIDTH = helpers.width(PACKET_HEADER_TYPE_IDX_HIGH, PACKET_HEADER_TYPE_IDX_LOW)
PACKET_OPCODE_IDX_HIGH = 28
PACKET_OPCODE_IDX_LOW = 27
PACKET_OPCODE_WIDTH = helpers.width(PACKET_OPCODE_IDX_HIGH, PACKET_OPCODE_IDX_LOW)
PACKET_TYPE_1_REGISTER_ADDRESS_IDX_HIGH = 26
PACKET_TYPE_1_REGISTER_ADDRESS_IDX_LOW = 13
PACKET_TYPE_1_REGISTER_ADDRESS_WIDTH = helpers.width(PACKET_TYPE_1_REGISTER_ADDRESS_IDX_HIGH, PACKET_TYPE_1_REGISTER_ADDRESS_IDX_LOW)
PACKET_TYPE_1_RESERVED_IDX_HIGH = 12
PACKET_TYPE_1_RESERVED_IDX_LOW = 11
PACKET_TYPE_1_RESERVED_WIDTH = helpers.width(PACKET_TYPE_1_RESERVED_IDX_HIGH, PACKET_TYPE_1_RESERVED_IDX_LOW)
PACKET_TYPE_1_WORD_COUNT_IDX_HIGH = 10
PACKET_TYPE_1_WORD_COUNT_IDX_LOW = 0
PACKET_TYPE_1_WORD_COUNT_WIDTH = helpers.width(PACKET_TYPE_1_WORD_COUNT_IDX_HIGH, PACKET_TYPE_1_WORD_COUNT_IDX_LOW)
PACKET_TYPE_2_WORD_COUNT_IDX_HIGH = 26
PACKET_TYPE_2_WORD_COUNT_IDX_LOW = 0
PACKET_TYPE_2_WORD_COUNT_WIDTH = helpers.width(PACKET_TYPE_2_WORD_COUNT_IDX_HIGH, PACKET_TYPE_2_WORD_COUNT_IDX_LOW)

# Packet format: UG570 table 9-16 and 9-18
class Type(enum.Enum):
  TYPE1 = 1
  TYPE2 = 2

# UG570: table 9-17
class Opcode(enum.Enum):
  NOOP = 0
  READ = 1
  WRITE = 2
  RSVD = 3

# UG570: table 9-19
# Note that some register addresses are undocumented in UG570. We use RSVD_XX
# for these undocumented indices.
class Register(enum.Enum):
  CRC = 0
  FAR = 1
  FDRI = 2
  FDRO = 3
  CMD = 4
  CTL0 = 5
  MASK = 6
  STAT = 7
  LOUT = 8
  COR0 = 9
  MFWR = 10
  CBC = 11
  IDCODE = 12
  AXSS = 13
  COR1 = 14
  RSVD_15 = 15
  WBSTAR = 16
  TIMER = 17
  RSVD_18 = 18
  RSVD_19 = 19
  RSVD_20 = 20
  RSVD_21 = 21
  BOOTSTS = 22
  RSVD_23 = 23
  CTL1 = 24
  RSVD_25 = 25
  RSVD_26 = 26
  RSVD_27 = 27
  RSVD_28 = 28
  RSVD_29 = 29
  # We call RSVD_30 the "SINKHOLE" register (not in UG570, this is our interpretation
  # as we always see it right before a bogus type-2 packet with a large word_count,
  # but this type-2 packet is immediately followed by dummy padding, the bus width
  # auto-detect pattern, and the sync_word, i.e., the start of a new bitstream).
  # So the type-2 packet is a "sinkhole" and isn't carrying valid data.
  RSVD_30 = 30
  BSPI = 31

# Packet format: UG570 table 9-22
# Note that some commands are undefined in UG570. We use RSVD_XX for these
# undocumented indices.
class Command(enum.Enum):
  NULL = 0
  WCFG = 1
  MFW = 2
  DGHIGH_LFRM = 3
  RCFG = 4
  START = 5
  URAM = 6
  RCRC = 7
  AGHIGH = 8
  SWITCH = 9
  GRESTORE = 10
  SHUTDOWN = 11
  RSVD_12 = 12
  DESYNC = 13
  RSVD_14 = 14
  IPROG = 15
  CRCC = 16
  LTIMER = 17
  BSPI_READ = 18
  FALL_EDGE = 19
  RSVD_20 = 20
  RSVD_21 = 21
  RSVD_22 = 22
  RSVD_23 = 23
  RSVD_24 = 24
  RSVD_25 = 25
  RSVD_26 = 26
  RSVD_27 = 27
  RSVD_28 = 28
  RSVD_29 = 29
  RSVD_30 = 30
  RSVD_31 = 31
