# author: Sahand Kashani <sahand.kashani@epfl.ch>

import numpy as np

import bitstream_spec as bit_spec
import helpers
import packet_spec as pkt_spec

# This package contains data structures to represent the various types of
# packets encoded in a Xilinx bitstream. This design is based entirely off
# of information in "UG570: UltraScale Configuration".

class Packet:
  def __init__(
    self,
    hdr_tpe: pkt_spec.Type,
    opcode: pkt_spec.Opcode,
    reg_addr: pkt_spec.Register | None,
    reserved: int | None,
    word_count: int,
    data: np.ndarray,
    byte_ofst: int
  ) -> None:
    # We expect a word-level array.
    assert data.dtype == bit_spec.BITSTREAM_ENDIANNESS, f"Error: Incorrect endianness."
    self.hdr_tpe = hdr_tpe
    self.opcode = opcode
    self.reg_addr = reg_addr
    self.reserved = reserved
    self.word_count = word_count
    self.data = data
    self.byte_ofst = byte_ofst

  def data_size_bytes(self) -> int:
    return self.data.nbytes

  def data_size_words(self) -> int:
    return self.data_size_bytes() // self.data.itemsize

  # Total packet size in bytes, including the header.
  def packet_size_bytes(self) -> int:
    # We add 4 bytes as the packet header is a 32-bit value.
    return self.data_size_bytes() + 4

  # Total packet size in words, including the header.
  def packet_size_words(self) -> int:
    return self.packet_size_bytes() // self.data.itemsize

  # Offset at which the payload starts within the packet.
  def data_ofst_bytes(self) -> int:
    # The header is a 32-bit value and the payload comes immediately after.
    return 4

  def __reconstruct_bin_hdr(self) -> str:
    if self.hdr_tpe == pkt_spec.Type.TYPE1:
      # Compute binary representation of every field with their actual bitwidth.
      # Python's f-strings allow using a custom width in the format.
      b_hdr_tpe = f"{self.hdr_tpe.value:0>{pkt_spec.PACKET_HEADER_TYPE_WIDTH}b}"
      b_opcode = f"{self.opcode.value:0>{pkt_spec.PACKET_OPCODE_WIDTH}b}"
      b_reg_addr = f"{self.reg_addr.value:0>{pkt_spec.PACKET_TYPE_1_REGISTER_ADDRESS_WIDTH}b}"
      b_reserved = f"{self.reserved:0>{pkt_spec.PACKET_TYPE_1_RESERVED_WIDTH}b}"
      b_word_count = f"{self.word_count:0>{pkt_spec.PACKET_TYPE_1_WORD_COUNT_WIDTH}b}"
      b_pkt = f"{b_hdr_tpe}{b_opcode}{b_reg_addr}{b_reserved}{b_word_count}"

    else:
      # Compute binary representation of every field with their actual bitwidth.
      # Python's f-strings allow using a custom width in the format.
      b_hdr_tpe = f"{self.hdr_tpe.value:0>{pkt_spec.PACKET_HEADER_TYPE_WIDTH}b}"
      b_opcode = f"{self.opcode.value:0>{pkt_spec.PACKET_OPCODE_WIDTH}b}"
      b_word_count = f"{self.word_count:0>{pkt_spec.PACKET_TYPE_2_WORD_COUNT_WIDTH}b}"
      b_pkt = f"{b_hdr_tpe}{b_opcode}{b_word_count}"

    return b_pkt

  def __reconstruct_hex_hdr(self) -> str:
    b_pkt = self.__reconstruct_bin_hdr()
    h_pkt = f"{int(b_pkt, 2):0>8x}"
    return h_pkt

  def __str__(self) -> str:
    if self.reg_addr == pkt_spec.Register.CMD:
      assert self.data.size == 1, f"Error: Expected write to CMD register to always have 1 word of payload, but found {self.data.size}"
      payload_str = pkt_spec.Command(self.data[0]).name

    else:
      # Not a command.

      # We test self.data.size instead of self.word_count as this packet could be
      # a type-2 packet that writes to the sinkhole register (RSVD_30). In such cases
      # the packet header has a large number in self.word_count, but this number
      # is incorrect and the payload doesn't really exist (it marks the end of a
      # SLR). So we check the actual size of the data payload instead.
      if self.data.size == 0:
        payload_str = ""
      elif self.data.size == 1:
        payload_str = f"0x{self.data[0]:0>8x}"
      else:
        if self.hdr_tpe == pkt_spec.Type.TYPE1:
          payload_str = ",".join([f"0x{x:0>8x}" for x in self.data])
        else:
          # data is larger than 1 word.
          # Contents can be very large, so we don't print them.
          payload_str = "..."

    # Bitwidth descriptions:
    # - header_type       => max "TYPE1"   => 5 chars
    # - word_count [10:0] => max 2047      => 4 decimal digits, but type-2 packet has 9 decimal digits, so we use the same here for consistency.
    # - word_count [26:0] => max 134217727 => 9 decimal digits
    # - opcode            => max "WRITE"   => 5 chars
    # - reg_addr          => max "BOOTSTS" => 7 chars
    pkt_hdr = self.__reconstruct_hex_hdr()
    return f"BYTE_OFST = 0x{self.byte_ofst:0>8x}, PKT_HEADER = 0x{pkt_hdr} (PKT_TYPE = {self.hdr_tpe.name:<5}, OP = {self.opcode.name:<5}, REG = {self.reg_addr.name:<7}, WORD_COUNT = {self.word_count:>9}), PKT_PAYLOAD = {{ {payload_str} }}"

  # Type-2
  # Factory method to create a packet.
  #
  # Don't know how to add circular type hint to THIS class, so I omit return type.
  @staticmethod
  def create_packet(
    word_bitstream: np.ndarray,
    word_ofst: int,
    packet_byte_ofst: int,
    # Used only to automatically infer the register address of type-2 packets
    # since long packets do not explicitly encode the target register (it is
    # implicitly defined as the register address of the closest type-1 packet).
    prev_reg_addr: pkt_spec.Register = None
  ):
    assert word_bitstream.dtype == bit_spec.BITSTREAM_ENDIANNESS, f"Error: Incorrect endianness."

    # The first word at the given offset is the packet header.
    packet_hdr = word_bitstream[word_ofst]

    # Must decode the header a simple "int" for now as we don't know yet if it's
    # a type-1 or type-2 packet, or some garbage. If it is garbage, then giving
    # the packet to the pkt_spec.Type() enum will throw an exception. Hence we
    # first check whether the packet type is valid and we will later wrap the
    # integer with pkt_spec.Type().
    hdr_tpe_int = helpers.bits(packet_hdr, pkt_spec.PACKET_HEADER_TYPE_IDX_HIGH, pkt_spec.PACKET_HEADER_TYPE_IDX_LOW)
    is_type_1_pkt = hdr_tpe_int == pkt_spec.Type.TYPE1.value
    is_type_2_pkt = hdr_tpe_int == pkt_spec.Type.TYPE2.value

    if is_type_1_pkt or is_type_2_pkt:
      hdr_tpe = pkt_spec.Type(hdr_tpe_int)
      opcode = pkt_spec.Opcode(helpers.bits(packet_hdr, pkt_spec.PACKET_OPCODE_IDX_HIGH, pkt_spec.PACKET_OPCODE_IDX_LOW))

      if is_type_1_pkt:
        # We isolate the fields in the packet header.
        reg_addr = pkt_spec.Register(helpers.bits(packet_hdr, pkt_spec.PACKET_TYPE_1_REGISTER_ADDRESS_IDX_HIGH, pkt_spec.PACKET_TYPE_1_REGISTER_ADDRESS_IDX_LOW))
        reserved = helpers.bits(packet_hdr, pkt_spec.PACKET_TYPE_1_RESERVED_IDX_HIGH, pkt_spec.PACKET_TYPE_1_RESERVED_IDX_LOW)
        word_count = helpers.bits(packet_hdr, pkt_spec.PACKET_TYPE_1_WORD_COUNT_IDX_HIGH, pkt_spec.PACKET_TYPE_1_WORD_COUNT_IDX_LOW)

        # We isolate the payload of the packet. We add 1 to word_ofst to avoid
        # capturing the packet header.
        packet_data_ofst_low = word_ofst + 1
        packet_data_ofst_high = word_ofst + 1 + word_count
        data = word_bitstream[packet_data_ofst_low:packet_data_ofst_high]

        return Packet(
          hdr_tpe=hdr_tpe,
          opcode=opcode,
          reg_addr=reg_addr,
          reserved=reserved,
          word_count=word_count,
          data=data,
          byte_ofst=packet_byte_ofst
        )

      elif is_type_2_pkt:
        # We isolate the fields in the packet header.
        word_count = helpers.bits(packet_hdr, pkt_spec.PACKET_TYPE_2_WORD_COUNT_IDX_HIGH, pkt_spec.PACKET_TYPE_2_WORD_COUNT_IDX_LOW)

        # A type-2 packet uses the address of the previous type-1 packet. If such a register
        # address does not exist, then something went wrong while parsing packets at the
        # caller.
        assert prev_reg_addr is not None, f"Error: Parsing type-2 packet failed as previous target register unknown!"

        # If a write to the "SINKHOLE" register occurs, then mark a flag that
        # indicates the next packet is the last one of this SLR and is in fact a
        # sinkhole (instead of a type-2 packet with a large word_count that
        # extends into the next SLR).
        is_sinkhole_write = (opcode == pkt_spec.Opcode.WRITE) and (prev_reg_addr == pkt_spec.Register.RSVD_30)

        if is_sinkhole_write:
          # The sinkhole has no payload (hence the name).
          data = np.array([], dtype=word_bitstream.dtype)
        else:
          # We isolate the payload of the packet. We add 1 to word_ofst to avoid
          # capturing the packet header.
          packet_data_ofst_low = word_ofst + 1
          packet_data_ofst_high = word_ofst + 1 + word_count
          data = word_bitstream[packet_data_ofst_low:packet_data_ofst_high]

        return Packet(
          hdr_tpe=hdr_tpe,
          opcode=opcode,
          reg_addr=prev_reg_addr,
          reserved=None,
          word_count=word_count,
          data=data,
          byte_ofst=packet_byte_ofst
        )

    else:
      # Not a type-1 or type-2 packet, so it is an invalid packet used for padding or something.

      # # Debug
      # print(f"Skipping invalid packet @ {packet_byte_ofst}")
      return None

# Returns True if the packet is a NOOP.
def is_noop_pkt(
  packet: Packet
) -> bool:
  return packet.opcode == pkt_spec.Opcode.NOOP

# Returns True if the packet is a write to the designated register. We do not
# check what is being written, just the fact that a write is occuring.
def is_reg_write_pkt(
  packet: Packet,
  reg_addr: pkt_spec.Register,
) -> bool:
  is_write_opcode = packet.opcode == pkt_spec.Opcode.WRITE
  is_target_reg = packet.reg_addr == reg_addr
  return is_write_opcode and is_target_reg

# Returns True if the packet is a write to the command register with a matching
# command code.
def is_reg_cmd_write_pkt(
  packet: Packet,
  cmd: pkt_spec.Command
) -> bool:
  is_write_to_cmd = is_reg_write_pkt(packet, pkt_spec.Register.CMD)
  is_target_cmd = (packet.data.size == 1) and (packet.data[0] == cmd.value)
  return is_write_to_cmd and is_target_cmd

# Returns True if the packet has no payload.
def is_empty_pkg(
  packet: Packet
) -> bool:
  return packet.data_size_words() == 0
