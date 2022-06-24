# author: Sahand Kashani <sahand.kashani@epfl.ch>

import enum


# Packet format: UG570 table 9-20 and 9-21.
# Note that some block types are undefined in UG570. We use RSVD_XX for these
# undocumented indices.
class FarBlockType(enum.Enum):
  CLB_IO_CLK = 0
  BRAM_CONTENT = 1
  RSVD_2 = 2
  RSVD_3 = 3
  RSVD_4 = 4
  RSVD_5 = 5
  RSVD_6 = 6
  RSVD_7 = 7
