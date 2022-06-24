# author: Sahand Kashani <sahand.kashani@epfl.ch>

import numpy as np

# Some information can be found at these addresses:
# - https://symbiflow.readthedocs.io/en/latest/prjxray/docs/architecture/bitstream_format.html
# - http://www.fpga-faq.com/FAQ_Pages/0026_Tell_me_about_bit_files.htm
#
# The header is stored is "Tag-Length-Value" (TLV) form. This is what TLV means
# (arbitrary numbers are used in the example).
#
#   08 04 72 26 9A 33
#   ^  ^  ^         ^
#   |  |  |---------|
#   |  |     value
#   |  - length
#   - tag
#
# In reality the whole bitstream header is *kinda* TLV as the first 3 fields do
# not have a tag. This is the format:
#
#   Field 1
#   2 bytes          length 0x0009           (big endian)
#   9 bytes          some sort of header     (including a trailing 0x00)
#
#   Field 2
#   2 bytes          length 0x0001
#   1 byte           key 0x61                (The letter "a")
#
#   All bitstreams are identical until this point. They diverge from here.
#
#   Field 3
#   2 bytes          length                                                 (value depends on file name length and options)
#   <length> bytes   string design name + options separated by semicolons
#                    <design_name>;COMPRESS=TRUE;...                        (including a trailing 0x00)
#
#   From here onwards it is TLV format.
#
#   Field 4
#   1 byte           key 0x62                (The letter "b")
#   2 bytes          length                  (value depends on part name length)
#   <length> bytes   string fpga part name   (including a trailing 0x00)
#
#   Field 5
#   1 byte           key 0x63                (The letter "c")
#   2 bytes          length
#   <length> bytes   string date             (including a trailing 0x00)
#
#   Field 6
#   1 byte           key 0x64                (The letter "d")
#   2 bytes          length
#   <length> bytes   string time             (including a trailing 0x00)
#
#   Field 7
#   1 byte           key 0x65                 (The letter "e")
#   4 bytes          length                   (value depends on device type, notice it is 4 bytes instead of 2).
#   <length> bytes   raw bit stream starting with 0xffffffff aa995566 syncword packets...

# LV format from here onwards.
HEADER_FIELD_1_LENGTH = 2
HEADER_FIELD_1_VALUE_EXPECTED = b"\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00"
HEADER_FIELD_2_LENGTH = 2
HEADER_FIELD_2_VALUE_EXPECTED = b"\x61"
# Field 3 = design name + options
HEADER_FIELD_3_LENGTH = 2
# TLV format from here onwards
# Field 4 = fpga part
HEADER_FIELD_4_TAG_LENGTH = 1
HEADER_FIELD_4_TAG_EXPECTED = b"\x62"
HEADER_FIELD_4_VALUE_LENGTH = 2
# Field 5 = date
HEADER_FIELD_5_TAG_LENGTH = 1
HEADER_FIELD_5_TAG_EXPECTED = b"\x63"
HEADER_FIELD_5_VALUE_LENGTH = 2
# Field 6 = time
HEADER_FIELD_6_TAG_LENGTH = 1
HEADER_FIELD_6_TAG_EXPECTED = b"\x64"
HEADER_FIELD_6_VALUE_LENGTH = 2
# Field 7 = bitstream
HEADER_FIELD_7_TAG_LENGTH = 1
HEADER_FIELD_7_TAG_EXPECTED = b"\x65"
HEADER_FIELD_7_VALUE_LENGTH = 4

# All information below is extracted from UG570.

# Big-endian 4-bytes
BITSTREAM_ENDIANNESS = np.dtype(">u4")

# These are 32-bit words, so we can view them as-is without using numpy byte arrays.
SYNC_WORD = 0xaa_99_55_66
DUMMY_WORD = 0xff_ff_ff_ff

# There are 2 frames of padding after the configuration of a row and before the
# next row starts. You can detect this padding by emitting a debug bitstream and
# looking at the last LOUT emitted in a row. If you attempt to parse the "packet"
# that follows, it will fail as there is no header (the data is all 0). There are
# 2 frames worth of empty words before the next valid header starts again.
#
# Equivalently, project X-Ray also documents this:
# https://f4pga.readthedocs.io/projects/prjxray/en/latest/architecture/configuration.html
#
#     At the end of a row, 2 frames of zeros must be inserted before data for the next row.
NUM_END_OF_ROW_PADDING_FRAMES = 2
