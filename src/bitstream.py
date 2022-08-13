# author: Sahand Kashani <sahand.kashani@epfl.ch>

import gzip
import itertools as iter
import math
from collections import defaultdict
from pathlib import Path

import more_itertools as miter
import numpy as np

import bitstream_spec as bit_spec
import packet as pkt
import packet_spec as pkt_spec
from arch_spec import ArchSpec
from frame import ConfigFrame, FrameAddressIncrementer, FrameAddressRegister

RawConfigurationArrays = dict[
  int, # IDCODE
  dict[
    FrameAddressRegister, # base FAR (not individual FARs!)
    list[ # A FAR can be written to multiple times, so we keep a list of writes (in order of appearance in the bitstream).
      tuple[
        int, # byte ofst in bitstream
        np.ndarray # configuration array (possibly multiple back-to-back frames)
      ]
    ]
  ]
]

# Writes to individual FARs are bucketized so it is easy to see if a FAR is
# written to multiple times (in a partial bitstream for example).
IndividualConfigurationArrays = dict[
  int, # IDCODE,
  dict[
    FrameAddressRegister, # per-frame FAR
    list[ # A FAR can be written to multiple times, so we keep a list of writes (in order of appearance in the bitstream).
      ConfigFrame # individual frame
    ]
  ]
]

class Bitstream:
  class Header:
    def __init__(
      self,
      bitstream: np.ndarray
    ) -> None:
      def parse_length_value(
        bitstream: np.ndarray,
        start_ofst: int,
        length_len: int
      ) -> bytes:
        value_len_bytes: bytes = bitstream[start_ofst : start_ofst + length_len].tobytes()
        value_len_int = int.from_bytes(value_len_bytes, "big")
        start_ofst += length_len
        value: bytes = bitstream[start_ofst : start_ofst + value_len_int].tobytes()
        return value

      def parse_tag_length_value(
        bitstream: np.ndarray,
        start_ofst: int,
        tag_len: int,
        length_len: int
      ) -> tuple[bytes, bytes]:
        tag: bytes = bitstream[start_ofst : start_ofst + tag_len].tobytes()
        start_ofst += tag_len
        value = parse_length_value(bitstream, start_ofst, length_len)
        return (tag, value)

      assert bitstream.itemsize == 1, f"Error: Expected 8-bit view of bitstream."
      start_ofst = 0

      # Length-Value (LV) format.

      field_1_value = parse_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_1_LENGTH)
      assert field_1_value == bit_spec.HEADER_FIELD_1_VALUE_EXPECTED, f"Error: Unexpected field 1 value {field_1_value}."
      start_ofst += bit_spec.HEADER_FIELD_1_LENGTH + len(field_1_value)

      field_2_value = parse_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_2_LENGTH)
      assert field_2_value == bit_spec.HEADER_FIELD_2_VALUE_EXPECTED, f"Error: Unexpected field 2 value {field_2_value}."
      start_ofst += bit_spec.HEADER_FIELD_2_LENGTH + len(field_2_value)

      field_3_value = parse_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_3_LENGTH)
      start_ofst += bit_spec.HEADER_FIELD_3_LENGTH + len(field_3_value)

      # Tag-Length-Value (TLV) format.

      (field_4_tag, field_4_value) = parse_tag_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_4_TAG_LENGTH, bit_spec.HEADER_FIELD_4_VALUE_LENGTH)
      assert field_4_tag == bit_spec.HEADER_FIELD_4_TAG_EXPECTED, f"Error: Unexpected field 4 tag {field_4_tag}."
      start_ofst += bit_spec.HEADER_FIELD_4_TAG_LENGTH + bit_spec.HEADER_FIELD_4_VALUE_LENGTH + len(field_4_value)

      (field_5_tag, field_5_value) = parse_tag_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_5_TAG_LENGTH, bit_spec.HEADER_FIELD_5_VALUE_LENGTH)
      assert field_5_tag == bit_spec.HEADER_FIELD_5_TAG_EXPECTED, f"Error: Unexpected field 5 tag {field_5_tag}."
      start_ofst += bit_spec.HEADER_FIELD_5_TAG_LENGTH + bit_spec.HEADER_FIELD_5_VALUE_LENGTH + len(field_5_value)

      (field_6_tag, field_6_value) = parse_tag_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_6_TAG_LENGTH, bit_spec.HEADER_FIELD_6_VALUE_LENGTH)
      assert field_6_tag == bit_spec.HEADER_FIELD_6_TAG_EXPECTED, f"Error: Unexpected field 6 tag {field_6_tag}."
      start_ofst += bit_spec.HEADER_FIELD_6_TAG_LENGTH + bit_spec.HEADER_FIELD_6_VALUE_LENGTH + len(field_6_value)

      (field_7_tag, field_7_value) = parse_tag_length_value(bitstream, start_ofst, bit_spec.HEADER_FIELD_7_TAG_LENGTH, bit_spec.HEADER_FIELD_7_VALUE_LENGTH)
      assert field_7_tag == bit_spec.HEADER_FIELD_7_TAG_EXPECTED, f"Error: Unexpected field 7 tag {field_7_tag}."
      start_ofst += bit_spec.HEADER_FIELD_7_TAG_LENGTH + bit_spec.HEADER_FIELD_7_VALUE_LENGTH + len(field_7_value)

      # Now that all fields have been extracted, we can parse the data they encode.

      def nul_terminated_byte_str_to_str(ntstr: bytes) -> str:
        # A bytes object, once indexed, returns an int. Hence why we test against 0 instead of b"\x00".
        assert ntstr[-1] == 0, f"Error: Expected null-terminated string, but received {ntstr}."
        # Strip nul character before decoding.
        return ntstr[:-1].decode("utf-8")

      design_and_options = nul_terminated_byte_str_to_str(field_3_value).split(";")
      # The elements are separated by semicolons. The first element is the name of
      # the design, all following elements are key-value-like options separated by
      # and "=" such as COMPRESS=TRUE, VERSION=2020.2, etc.
      name = design_and_options[0]
      options = dict()
      for option in design_and_options[1:]:
        (k, v) = option.split("=")
        options[k] = v

      self.name: str = name
      self.options: dict[str, str] = options
      self.fpga_part: str = nul_terminated_byte_str_to_str(field_4_value)
      self.date: str = nul_terminated_byte_str_to_str(field_5_value)
      self.time: str = nul_terminated_byte_str_to_str(field_6_value)

      # The bitstream data starts where field_7's value starts.
      self.bitstream_data_ofst: int = start_ofst - len(field_7_value)

    def get_option(self, key: str) -> str | None:
      return self.options.get(key)

  def __init__(
    self,
    byte_bitstream: np.ndarray
  ) -> None:
    # Reads and splits a bitstream into
    #
    #   (1) the text header
    #   (2) the bitstream data
    #
    # The bitstream's internal packets are also decoded.
    #
    # Args:
    # - byte_bitstream: np.ndarray
    #     Byte-view of a bitstream.
    assert byte_bitstream.itemsize == 1, f"Error: Expected 8-bit view of bitstream."

    # Decode header.
    hdr = Bitstream.Header(byte_bitstream)

    # Decode packets.
    bitstream_data = byte_bitstream[hdr.bitstream_data_ofst:]
    packets = Bitstream.__decode_all_packets(bitstream_data)
    # Transform relative offsets from start of bitstream data into absolute
    # offsets within the bitstream.
    for packet in packets:
      packet.byte_ofst += hdr.bitstream_data_ofst

    self._hdr = hdr
    self._hdr_byte_ofst = 0
    self._data_byte_ofst = hdr.bitstream_data_ofst
    # Tuple so packet order cannot be changed
    self._packets = tuple(packets)

    # Lazy evaluation. These properties will be computed the first time they are
    # requested.
    self._has_crc: bool | None = None
    self._is_per_frame_crc: bool | None = None
    self._idcodes: set[int] = set()
    self._raw_configuration_arrays: RawConfigurationArrays | None = None
    self._individual_configuration_arrays: IndividualConfigurationArrays | None = None

  @property
  def header(self):
    return self._hdr

  @property
  def packets(self):
    return self._packets

  @staticmethod
  def from_file_path(
    bitstream_path: str | Path
  ):
    if Path(bitstream_path).suffix == ".gz":
      # Decompress file in memory before creating a bitstream object.
      with gzip.open(bitstream_path, "rb") as f:
        data = f.read()
    else:
      with open(bitstream_path, "rb") as f:
        data = f.read()

    return Bitstream.from_string(data)

  @staticmethod
  def from_string(
    bstr: bytes
  ):
    # We parse the bitstream as uint8 (instead of uint32) as it contains unsynchronized
    # data and we must look for the SYNC WORD before we can interpret the contents
    # as 32-bit words.
    byte_bitstream = np.fromstring(bstr, dtype=np.uint8)
    return Bitstream(byte_bitstream)

  # Finds the byte offsets of all SYNC WORDs in the given array.
  #
  # Args:
  # - byte_bitstream: np.ndarray
  #     Byte-level view of a bitstream.
  #
  # Returns:
  # - ofsts: List[int]
  #     List of byte offsets at which a SYNC WORD was found.
  @staticmethod
  def __find_sync_word_ofsts(
    byte_bitstream: np.ndarray
  ) -> list[int]:
    assert byte_bitstream.itemsize == 1, f"Error: Expected 8-bit view of bitstream."

    # We must find the SYNC WORD in the array. This word may not be word-aligned,
    # so we need to look through a 4-byte sliding window to find it. This is expensive,
    # but there is alternative.
    byte_sliding_window = np.lib.stride_tricks.sliding_window_view(byte_bitstream, 4)

    # We need to convert the 32-bit sync word into an array of 4 bytes so we can
    # match each entry with the 4 elements in the sliding window.
    sync_word_byte_view = np.array([bit_spec.SYNC_WORD], dtype=bit_spec.BITSTREAM_ENDIANNESS).view(dtype=np.uint8)

    # The sliding window is a 2D ndarray, so we call flatten() to have a 1D result
    # as each dimension will have just 1 number after np.all() and np.argwhere are
    # executed.
    sync_word_byte_ofsts = np.argwhere(
      np.all(byte_sliding_window == sync_word_byte_view, axis=-1)
    ).flatten()

    return sync_word_byte_ofsts.tolist()

  # Returns the next SYNC WORD found that is located at least at `min_byte_ofst`.
  #
  # Args:
  # - sync_word_byte_ofsts: List[int]
  #     List of SYNC WORD positions.
  # - min_byte_ofst: int
  #     Minimum byte offset at which the new SYNC WORD should be located.
  #
  # Returns:
  # - ofst: int | None
  #     The offset of the next SYNC WORD, or None if no SYNC WORD exists that
  #     satisfies this criteria.
  @staticmethod
  def __find_next_sync_word(
    sync_word_byte_ofsts: list[int],
    min_byte_ofst: int
  ) -> int | None:
    candidate_sync_word_byte_ofsts = [ofst for ofst in sync_word_byte_ofsts if min_byte_ofst <= ofst]
    if len(candidate_sync_word_byte_ofsts) == 0:
      return None
    else:
      return min(candidate_sync_word_byte_ofsts)

  # Decodes all packets found in the input array until the next boundary is found.
  # We define a boundary as a DESYNC command packet being found.
  #
  # Args:
  # - word_bitstream: np.ndarray
  #     Word-level view of a bitstream.
  #
  # Returns:
  # - packets: List[pkt.Packet]
  #     Packets found. The packets are "placed" at an offset relative to the input array.
  #     Note that NOOP packets are skipped as they are just noise.
  @staticmethod
  def __decode_packets_until_next_boundary(
    word_bitstream: np.ndarray,
  ) -> list[pkt.Packet]:
    assert word_bitstream.dtype == bit_spec.BITSTREAM_ENDIANNESS, f"Error: Incorrect endianness."

    packets: list[pkt.Packet] = list()

    # Start decoding packets until you see a boundary command. Note that we may
    # sometimes see dummy/sync words instead of a packet, in which case the word
    # should be skipped.

    boundary_found = False
    word_ofst = 0
    current_reg_addr = None

    while not boundary_found:
      packet_byte_ofst = word_ofst * word_bitstream.itemsize
      packet = pkt.Packet.create_packet(word_bitstream, word_ofst, packet_byte_ofst, current_reg_addr)

      if packet is None:
        # Not a packet.

        # If creating a packet failed, then we just increment the word ofst and
        # continue. Packet creation can fail if we encounter sync/dummy words, or
        # if we encounter 0 padding (like at the end of a row's frames before the
        # next row's frame starts).
        word_ofst += 1

      else:
        # Decode packet.

        # Type-2 packets that could arrive after this packet use the address of
        # the preceding type-1 packet, so we save it for future iterations.
        if packet.hdr_tpe == pkt_spec.Type.TYPE1:
          current_reg_addr = packet.reg_addr

        # Stop decoding if DESYNC command found or if this is the actual sinkhole
        # packet (not the packet that announces the sinkhole, but the actual
        # sinkhole itself).
        is_desync_cmd = pkt.is_reg_cmd_write_pkt(packet, pkt_spec.Command.DESYNC)
        if is_desync_cmd:
          boundary_found = True

        # Record packet. We don't store NOOPs as they are just noise.
        if not pkt.is_noop_pkt(packet):
          packets.append(packet)

        word_ofst += packet.packet_size_words()

    return packets

  # Decodes all packets found in the bitstream. This includes discontinuous packets
  # separated by large gaps (as could exist in multi-SLR FPGAs).
  #
  # Args:
  # - byte_bitstream: np.ndarray
  #     Bitstream data.
  #
  # Returns:
  # - packets: List[pkt.Packet]
  #     List of all packets decoded in the bitstream. Note that NOOP packets are
  #     not returned as they are just noise.
  @staticmethod
  def __decode_all_packets(
    byte_bitstream: np.ndarray
  ) -> list[pkt.Packet]:
    assert byte_bitstream.itemsize == 1, f"Error: Expected 8-bit view of bitstream."

    packets = list[pkt.Packet]()

    # We start by finding all SYNC_WORDs in the bitstream. Note that it is expensive
    # to find the sync words, so we only do it once and keep track of their offsets.

    # IMPORTANT: It is possible that the SYNC_WORD appears as a pattern in the FPGA
    # configuration itself (a word written in the FDRI register). Therefore not all
    # the offsets we find below correspond to true SYNC_WORDs and we'll need to
    # skip some entries later if we detect they are located in an FPGA configuration
    # packet.
    all_sync_word_byte_ofsts = Bitstream.__find_sync_word_ofsts(byte_bitstream)
    assert len(all_sync_word_byte_ofsts) > 0, f"Error: Did not find any SYNC_WORDs in the bitstream."
    current_sync_word_byte_ofst = all_sync_word_byte_ofsts[0]

    sync_words_exist = True
    while sync_words_exist:
      # Start from the position of the current SYNC_WORD and view the bitstream as
      # an array of words (instead of bytes) as all contents are word-aligned from
      # here onwards.
      word_sub_bitstream: np.ndarray = byte_bitstream[current_sync_word_byte_ofst:].view(dtype=bit_spec.BITSTREAM_ENDIANNESS)

      sub_packets = Bitstream.__decode_packets_until_next_boundary(word_sub_bitstream)

      # The sub-packets found above are positioned relatively to the SYNC_WORD. We
      # now transform these positions into relative offsets from the start of the
      # bitstream.
      for sub_packet in sub_packets:
        sub_packet.byte_ofst += current_sync_word_byte_ofst

      # Remember packets we've decoded until now.
      packets.extend(sub_packets)

      # Now that we have found all packets until a boundary packet, we need to look
      # for the next SYNC_WORD.
      # We pre-computed the location of all SYNC_WORDs before, but remember that
      # the SYNC_WORD itself could have appeared inside an FPGA configuration packet.
      # We therefore need to scan through all SYNC_WORD positions we previously
      # found and select the first one that is larger than the offset at which the
      # boundary packet is found.
      boundary_pkt = sub_packets[-1]
      after_boundary_byte_ofst = boundary_pkt.byte_ofst + boundary_pkt.packet_size_bytes()
      current_sync_word_byte_ofst = Bitstream.__find_next_sync_word(all_sync_word_byte_ofsts, after_boundary_byte_ofst)
      if current_sync_word_byte_ofst is None:
        sync_words_exist = False

    return packets

  def is_encrypted(self) -> bool:
    # UG908 table 41: BITSTREAM.ENCRYPTION.ENCRYPT default is "NO"
    key = "ENCRYPT"
    return self.header.get_option(key) == "YES"

  def is_compressed(self) -> bool:
    # UG908 table 41: BITSTREAM.GENERAL.COMPRESS default is "FALSE"
    key = "COMPRESS"
    return self.header.get_option(key) == "TRUE"

  def get_user_id(self) -> str | None:
    key = "UserID"
    return self.header.get_option(key)

  def get_version(self) -> str | None:
    key = "Version"
    return self.header.get_option(key)

  def is_crc_enabled(self) -> bool:
    if self._has_crc is None:
      for packet in self.packets:
        if pkt.is_reg_write_pkt(packet, pkt_spec.Register.CRC):
          self._has_crc = True
          return True

      self._has_crc = False

    return self._has_crc

  def is_partial(self) -> bool:
    key = "PARTIAL"
    return self.header.get_option(key) == "TRUE"

  def is_per_frame_crc(self) -> bool:
    if self._is_per_frame_crc is None:
      ar_spec = ArchSpec.create_spec(self.header.fpga_part)

      # A bitstream with per-frame CRCs writes every frame individually to the FDRI register.
      # The write to FDRI is followed (perhaps not immediately) by a write to the CRC register.

      # We first check that every write to FDRI consists of a single frame each time.
      for packet in self.packets:
        if pkt.is_reg_write_pkt(packet, pkt_spec.Register.FDRI):
          if packet.data_size_words() != ar_spec.frame_size_words():
            self._is_per_frame_crc = False
            # Early-exit.
            return self._is_per_frame_crc

      # Now that we know all writes to FDRI are single frames, we need to check that
      # every frame has an associated CRC packet.
      fdri_packets_idx = (
        idx for (idx, packet) in enumerate(self.packets)
        if pkt.is_reg_write_pkt(packet, pkt_spec.Register.FDRI)
      )

      crc_packets_idx = (
        idx for (idx, packet) in enumerate(self.packets)
        if pkt.is_reg_write_pkt(packet, pkt_spec.Register.CRC)
      )
      # Some bitstreams may not have enough writes to CRC and are therefore not
      # per-frame CRC bitstreams. Such bitstreams would run out of entries before
      # all FDRI packets are seen, therefore causing the while loop in the sliding
      # window below to fail at some point when next() is called.
      # Chaining the generator with math.inf will avoid the exception and cause
      # a clean exit from the while loop.
      crc_packets_idx = iter.chain(
        crc_packets_idx,
        iter.repeat(math.inf)
      )

      for (prev_fdri_idx, next_fdri_idx) in miter.windowed(fdri_packets_idx, n=2):
        # Advance past prev_fdri_idx
        while (crc_idx := next(crc_packets_idx)) < prev_fdri_idx: pass
        if next_fdri_idx < crc_idx:
          self._is_per_frame_crc = False
          # Early-exit.
          return self._is_per_frame_crc

      # The loop above handles all (prev_fdri, next_fdri) tuples. We also need to
      # check if the very last write to CRC (that occurs after the last "next_fdri")
      # also exists. So we now advance the crc pointer past "next_fdri" (instead
      # of past "prev_fdri" and check that such an crc exists.
      while (crc_idx := next(crc_packets_idx)) < next_fdri_idx: pass
      if crc_idx == math.inf:
        self._is_per_frame_crc = False
        # Early-exit.
        return self._is_per_frame_crc

      self._is_per_frame_crc = True

    return self._is_per_frame_crc

  def get_idcodes(
    self
  ) -> set[int]:
    if len(self._idcodes) == 0:
      idcodes = set()

      for packet in self.packets:
        if pkt.is_reg_write_pkt(packet, pkt_spec.Register.IDCODE):
          idcode = packet.data[0]
          idcodes.add(idcode)

      self._idcodes = idcodes

    return self._idcodes

  # This returns ALL configuration frames, including any zero padding frames that exist between rows.
  def get_raw_configuration_arrays(self) -> RawConfigurationArrays:
    assert not self.is_compressed(), f"Error: Can only extract configuration arrays if bitstream is not compressed!"

    # The algorithm below assumes writes to the FDRI register auto-increment FAR. However, in bitstreams with per-frame
    # CRCs, the FAR register (which FDRI just wrote to) is written *after* FDRI again with its previous value, then is
    # followed by a CRC. Here's an example:
    #
    #   PKT_HEADER = 0x30008001 (PKT_TYPE = TYPE1, OP = WRITE, REG = CMD    , WORD_COUNT =         1), PKT_PAYLOAD = { WCFG }
    #   PKT_HEADER = 0x30002001 (PKT_TYPE = TYPE1, OP = WRITE, REG = FAR    , WORD_COUNT =         1), PKT_PAYLOAD = { 0x00000000 }
    #   PKT_HEADER = 0x3000407b (PKT_TYPE = TYPE1, OP = WRITE, REG = FDRI   , WORD_COUNT =       123), PKT_PAYLOAD = { 0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000010,0x00000000 }
    #   PKT_HEADER = 0x30002001 (PKT_TYPE = TYPE1, OP = WRITE, REG = FAR    , WORD_COUNT =         1), PKT_PAYLOAD = { 0x00000000 } (FAR 0 was written to by the write to FDRI above)
    #   PKT_HEADER = 0x30000001 (PKT_TYPE = TYPE1, OP = WRITE, REG = CRC    , WORD_COUNT =         1), PKT_PAYLOAD = { 0x034886f2 } (this write to CRC *probably* increments FAR internally, but I cannot check)
    #   PKT_HEADER = 0x3000407b (PKT_TYPE = TYPE1, OP = WRITE, REG = FDRI   , WORD_COUNT =       123), PKT_PAYLOAD = { 0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000,0x00000000 }
    #   PKT_HEADER = 0x30002001 (PKT_TYPE = TYPE1, OP = WRITE, REG = FAR    , WORD_COUNT =         1), PKT_PAYLOAD = { 0x00000001 } (FAR 1 was written to by the write to FDRI above)
    #   PKT_HEADER = 0x30000001 (PKT_TYPE = TYPE1, OP = WRITE, REG = CRC    , WORD_COUNT =         1), PKT_PAYLOAD = { 0x06b1285e } (this write to CRC *probably* increments FAR internally, but I cannot check)
    #
    # The decoding algorithm would not work in such cases. I suspect writing to CRC actually increments FAR internally,
    # but I cannot check this. Therefore I will only support extracting frames from a bitstream that does not use
    # per-frame CRCs.
    assert not self.is_per_frame_crc(), f"Error: Can only extract configuration arrays if bitstream does not contain per-frame CRCs!"

    if self._raw_configuration_arrays is None:
      ar_spec = ArchSpec.create_spec(self.header.fpga_part)

      idcode_far_configArrays: RawConfigurationArrays = defaultdict(
        lambda: defaultdict(list)
      )

      current_idcode: int | None = None
      current_far: FrameAddressRegister | None = None

      for packet in self.packets:
        if pkt.is_reg_write_pkt(packet, pkt_spec.Register.IDCODE):
          current_idcode = packet.data[0]

        elif pkt.is_reg_write_pkt(packet, pkt_spec.Register.FAR):
          current_far = FrameAddressRegister.from_int(packet.data[0], ar_spec)

        # The check of the packet not being empty is so we can skip type-1 packets
        # that have an empty payload as they just are placeholders for the next
        # packet that is a long type-2 packet.
        elif pkt.is_reg_write_pkt(packet, pkt_spec.Register.FDRI) and not pkt.is_empty_pkg(packet):
          assert current_idcode is not None, f"Error: IDCODE is still undefined before config frame is seen at byte ofst {packet.byte_ofst}."
          assert current_far is not None, f"Error: FAR is still undefined before config frame is seen at byte ofst {packet.byte_ofst}."

          # A packet can contain multiple frames back-to-back. We first check that
          # the total frame size is a multiple of a single frame size as a sanity
          # check.
          configArray_byte_ofst = packet.byte_ofst + packet.data_ofst_bytes()
          configArray = packet.data
          assert configArray.size % ar_spec.frame_size_words() == 0, f"Error: Expected config array at byte ofst {configArray_byte_ofst} to be a multiple of {ar_spec.frame_size_words()} words, but is {configArray.size} words"

          idcode_far_configArrays[current_idcode][current_far].append((configArray_byte_ofst, configArray))

      self._raw_configuration_arrays = idcode_far_configArrays

    return self._raw_configuration_arrays

  # Returns all configuration frames in the bitstream.
  def get_per_far_configuration_arrays(
    self
  ) -> IndividualConfigurationArrays:
    if self._individual_configuration_arrays is None:
      ar_spec = ArchSpec.create_spec(self.header.fpga_part)
      far_incrementer = FrameAddressIncrementer(self.header.fpga_part)

      idcode_far_frames: IndividualConfigurationArrays = defaultdict(
        lambda: defaultdict(list)
      )

      raw_config = self.get_raw_configuration_arrays()
      for (idcode, baseFars_dict) in raw_config.items():
        for (far, byteOfstConfigArrayList) in baseFars_dict.items():
          for (base_byte_ofst, config_array) in byteOfstConfigArrayList:

            # A config array can contain multiple frames back-to-back. We split the
            # large array into individual frames and assign a dedicated FAR to each
            # here.
            singleframes = config_array.reshape(-1, ar_spec.frame_size_words())

            singleframes_idx = 0
            while singleframes_idx < len(singleframes):
              frame = singleframes[singleframes_idx]
              frame_byte_ofst = base_byte_ofst + singleframes_idx * ar_spec.frame_size_words() * singleframes.itemsize

              config_frame = ConfigFrame(frame_byte_ofst, frame, far, ar_spec)

              # Keep track of frame as belonging to specific IDCODE.
              # idcode_far_frames[idcode][config_frame.far.to_int()].append(config_frame)
              idcode_far_frames[idcode][config_frame.far].append(config_frame)
              singleframes_idx += 1

              if far_incrementer.is_last_far_of_row(idcode, far):
                # There are empty padding frames at the end of every row. We must
                # skip them in the next iterations otherwise we'll offset the
                # configuration frames.
                # As a sanity check, I ensure that I'm indeed skipping empty frames.
                for emptyFrame_idx in range(bit_spec.NUM_END_OF_ROW_PADDING_FRAMES):
                  frame = singleframes[singleframes_idx]
                  frame_byte_ofst = base_byte_ofst + singleframes_idx * ar_spec.frame_size_words() * singleframes.itemsize
                  frame_is_zero = not np.any(frame)
                  assert frame_is_zero, f"Error: Expected end-of-row frame at BYTE_OFST {frame_byte_ofst} to be all-zeros!"
                  singleframes_idx += 1

              # Auto-increment FAR after every frame since this is a write to FDRI.
              far = far_incrementer.increment(idcode, far)

      self._individual_configuration_arrays = idcode_far_frames

    return self._individual_configuration_arrays