module bram_array();

  parameter G_SIZE = 4;

  wire fake_clock;
  // wire [63 : 0] tmp [G_SIZE-1 : 0];
  wire [15 : 0] tmp_A [G_SIZE-1 : 0];
  wire [15 : 0] tmp_B [G_SIZE-1 : 0];

  // This FDRE is used as an "active" signal for the BRAM's clock signal, otherwise
  // Vivado will fail a DRC check when generating the bitstream.
  (* DONT_TOUCH = "yes" *)
  FDRE #(
    .INIT(1'b0),
    .IS_C_INVERTED(1'b0),
    .IS_D_INVERTED(1'b0),
    .IS_R_INVERTED(1'b0)
  )
  FDRE_inst (
    .Q(fake_clock),
    .C(1'b0),
    .CE(1'b0),
    .D(~fake_clock),
    .R(1'b0)
  );

  genvar i;
  generate
    for (i=0; i<G_SIZE; i=i+1) begin : bram_gen

      // RAMB18E2: 18K-bit Configurable Synchronous Block RAM UltraScale
      (* DONT_TOUCH = "yes" *)
      RAMB18E2 #(
        // CASCADE_ORDER_A, CASCADE_ORDER_B: "FIRST", "MIDDLE", "LAST", "NONE"
        .CASCADE_ORDER_A("NONE"),
        .CASCADE_ORDER_B("NONE"),
        // CLOCK_DOMAINS: "COMMON", "INDEPENDENT"
        .CLOCK_DOMAINS("COMMON"),
        // Collision check: "ALL", "GENERATE_X_ONLY", "NONE", "WARNING_ONLY"
        .SIM_COLLISION_CHECK("ALL"),
        // DOA_REG, DOB_REG: Optional output register (0, 1)
        .DOA_REG(1),
        .DOB_REG(1),
        // ENADDRENA/ENADDRENB: Address enable pin enable, "TRUE", "FALSE"
        .ENADDRENA("FALSE"),
        .ENADDRENB("FALSE"),
        // INITP_00 to INITP_07: Initial contents of parity memory array
        .INITP_00(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_01(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_02(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_03(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_04(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_05(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_06(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INITP_07(256'h0000000000000000000000000000000000000000000000000000000000000000),
        // INIT_00 to INIT_3F: Initial contents of data memory array
        .INIT_00(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_01(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_02(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_03(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_04(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_05(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_06(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_07(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_08(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_09(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_0A(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_0B(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_0C(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_0D(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_0E(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_0F(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_10(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_11(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_12(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_13(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_14(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_15(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_16(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_17(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_18(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_19(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_1A(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_1B(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_1C(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_1D(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_1E(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_1F(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_20(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_21(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_22(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_23(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_24(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_25(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_26(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_27(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_28(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_29(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_2A(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_2B(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_2C(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_2D(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_2E(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_2F(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_30(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_31(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_32(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_33(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_34(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_35(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_36(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_37(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_38(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_39(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_3A(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_3B(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_3C(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_3D(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_3E(256'h0000000000000000000000000000000000000000000000000000000000000000),
        .INIT_3F(256'h0000000000000000000000000000000000000000000000000000000000000000),
        // INIT_A, INIT_B: Initial values on output ports
        .INIT_A(18'h00000),
        .INIT_B(18'h00000),
        // Initialization File: RAM initialization file
        .INIT_FILE("NONE"),
        // Programmable Inversion Attributes: Specifies the use of the built-in programmable inversion
        .IS_CLKARDCLK_INVERTED(1'b0),
        .IS_CLKBWRCLK_INVERTED(1'b0),
        .IS_ENARDEN_INVERTED(1'b0),
        .IS_ENBWREN_INVERTED(1'b0),
        .IS_RSTRAMARSTRAM_INVERTED(1'b0),
        .IS_RSTRAMB_INVERTED(1'b0),
        .IS_RSTREGARSTREG_INVERTED(1'b0),
        .IS_RSTREGB_INVERTED(1'b0),
        // RDADDRCHANGE: Disable memory access when output value does not change ("TRUE", "FALSE")
        .RDADDRCHANGEA("FALSE"),
        .RDADDRCHANGEB("FALSE"),
        // READ_WIDTH_A/B, WRITE_WIDTH_A/B: Read/write width per port
        .READ_WIDTH_A(0), // 0, 1, 2, 4, 9, 18, 36 (UG974 pg 595, yes this port supports 36 and the others do not)
        .READ_WIDTH_B(0), // 0, 1, 2, 4, 9, 18
        .WRITE_WIDTH_A(0), // 0, 1, 2, 4, 9, 18
        .WRITE_WIDTH_B(0), // 0, 1, 2, 4, 9, 18, 36 (UG974 pg 595, yes this port supports 36 and the others do not)
        // RSTREG_PRIORITY_A, RSTREG_PRIORITY_B: Reset or enable priority ("RSTREG", "REGCE")
        .RSTREG_PRIORITY_A("RSTREG"),
        .RSTREG_PRIORITY_B("RSTREG"),
        // SRVAL_A, SRVAL_B: Set/reset value for output
        .SRVAL_A(18'h00000),
        .SRVAL_B(18'h00000),
        // Sleep Async: Sleep function asynchronous or synchronous ("TRUE", "FALSE")
        .SLEEP_ASYNC("FALSE"),
        // WriteMode: "WRITE_FIRST", "NO_CHANGE", "READ_FIRST"
        .WRITE_MODE_A("NO_CHANGE"),
        .WRITE_MODE_B("NO_CHANGE")
      )
      RAMB18E2_inst (
        // Cascade Signals outputs: Multi-BRAM cascade signals
        .CASDOUTA(),            // 16-bit output: Port A cascade output data
        .CASDOUTB(),            // 16-bit output: Port B cascade output data
        .CASDOUTPA(),           // 2-bit output: Port A cascade output parity data
        .CASDOUTPB(),           // 2-bit output: Port B cascade output parity data
        // Port A Data outputs: Port A data
        .DOUTADOUT(tmp_A[i]),   // 16-bit output: Port A data/LSB data
        .DOUTPADOUTP(),         // 2-bit output: Port A parity/LSB parity
        // Port B Data outputs: Port B data
        .DOUTBDOUT(tmp_B[i]),   // 16-bit output: Port B data/MSB data
        .DOUTPBDOUTP(),         // 2-bit output: Port B parity/MSB parity
        // Cascade Signals inputs: Multi-BRAM cascade signals
        .CASDIMUXA(),           // 1-bit input: Port A input data (0=DINA, 1=CASDINA)
        .CASDIMUXB(),           // 1-bit input: Port B input data (0=DINB, 1=CASDINB)
        .CASDINA(),             // 16-bit input: Port A cascade input data
        .CASDINB(),             // 16-bit input: Port B cascade input data
        .CASDINPA(),            // 2-bit input: Port A cascade input parity data
        .CASDINPB(),            // 2-bit input: Port B cascade input parity data
        .CASDOMUXA(),           // 1-bit input: Port A unregistered data (0=BRAM data, 1=CASDINA)
        .CASDOMUXB(),           // 1-bit input: Port B unregistered data (0=BRAM data, 1=CASDINB)
        .CASDOMUXEN_A(),        // 1-bit input: Port A unregistered output data enable
        .CASDOMUXEN_B(),        // 1-bit input: Port B unregistered output data enable
        .CASOREGIMUXA(),        // 1-bit input: Port A registered data (0=BRAM data, 1=CASDINA)
        .CASOREGIMUXB(),        // 1-bit input: Port B registered data (0=BRAM data, 1=CASDINB)
        .CASOREGIMUXEN_A(),     // 1-bit input: Port A registered output data enable
        .CASOREGIMUXEN_B(),     // 1-bit input: Port B registered output data enable
        // Port A Address/Control Signals inputs: Port A address and control signals
        .ADDRARDADDR(14'b0),    // 14-bit input: A/Read port address
        .ADDRENA(1'b0),         // 1-bit input: Active-High A/Read port address enable
        .CLKARDCLK(fake_clock), // 1-bit input: A/Read port clock
        .ENARDEN(1'b0),         // 1-bit input: Port A enable/Read enable
        .REGCEAREGCE(1'b0),     // 1-bit input: Port A register enable/Register enable
        .RSTRAMARSTRAM(1'b0),   // 1-bit input: Port A set/reset
        .RSTREGARSTREG(1'b0),   // 1-bit input: Port A register set/reset
        .WEA(2'b0),             // 2-bit input: Port A write enable
        // Port A Data inputs: Port A data
        .DINADIN(tmp_A[i]),     // 16-bit input: Port A data/LSB data
        .DINPADINP(2'b0),       // 2-bit input: Port A parity/LSB parity
        // Port B Address/Control Signals inputs: Port B address and control signals
        .ADDRBWRADDR(14'b0),    // 14-bit input: B/Write port address
        .ADDRENB(1'b0),         // 1-bit input: Active-High B/Write port address enable
        .CLKBWRCLK(fake_clock), // 1-bit input: B/Write port clock
        .ENBWREN(1'b0),         // 1-bit input: Port B enable/Write enable
        .REGCEB(1'b0),          // 1-bit input: Port B register enable
        .RSTRAMB(1'b0),         // 1-bit input: Port B set/reset
        .RSTREGB(1'b0),         // 1-bit input: Port B register set/reset
        .SLEEP(1'b0),           // 1-bit input: Sleep Mode
        .WEBWE(4'b0),           // 4-bit input: Port B write enable/Write enable
        // Port B Data inputs: Port B data
        .DINBDIN(tmp_B[i]),     // 16-bit input: Port B data/MSB data
        .DINPBDINP(2'b0)        // 2-bit input: Port B parity/MSB parity
      );

    //   // FIFO36E2: 36K FIFO (First-In-First-Out) Block RAM Memory UltraScale
    //   (* DONT_TOUCH = "yes" *)
    //   FIFO36E2 #(
    //     .CASCADE_ORDER("NONE"),            // FIRST, LAST, MIDDLE, NONE, PARALLEL
    //     .CLOCK_DOMAINS("COMMON"),          // COMMON, INDEPENDENT
    //     .EN_ECC_PIPE("FALSE"),             // ECC pipeline register, (FALSE, TRUE)
    //     .EN_ECC_READ("FALSE"),             // Enable ECC decoder, (FALSE, TRUE)
    //     .EN_ECC_WRITE("FALSE"),            // Enable ECC encoder, (FALSE, TRUE)
    //     .FIRST_WORD_FALL_THROUGH("FALSE"), // FALSE, TRUE
    //     .INIT(72'h000000000000000000),     // Initial values on output port
    //     .PROG_EMPTY_THRESH(256),           // Programmable Empty Threshold
    //     .PROG_FULL_THRESH(256),            // Programmable Full Threshold
    //     // Programmable Inversion Attributes: Specifies the use of the built-in programmable inversion
    //     .IS_RDCLK_INVERTED(1'b0),          // Optional inversion for RDCLK
    //     .IS_RDEN_INVERTED(1'b0),           // Optional inversion for RDEN
    //     .IS_RSTREG_INVERTED(1'b0),         // Optional inversion for RSTREG
    //     .IS_RST_INVERTED(1'b0),            // Optional inversion for RST
    //     .IS_WRCLK_INVERTED(1'b0),          // Optional inversion for WRCLK
    //     .IS_WREN_INVERTED(1'b0),           // Optional inversion for WREN
    //     .RDCOUNT_TYPE("RAW_PNTR"),         // EXTENDED_DATACOUNT, RAW_PNTR, SIMPLE_DATACOUNT, SYNC_PNTR
    //     .READ_WIDTH(72),                   // 4, 9, 18, 36, 72
    //     .REGISTER_MODE("UNREGISTERED"),    // DO_PIPELINED, REGISTERED, UNREGISTERED
    //     .RSTREG_PRIORITY("RSTREG"),        // REGCE, RSTREG
    //     .SLEEP_ASYNC("FALSE"),             // FALSE, TRUE
    //     .SRVAL(72'h000000000000000000),    // SET/reset value of the FIFO outputs
    //     .WRCOUNT_TYPE("RAW_PNTR"),         // EXTENDED_DATACOUNT, RAW_PNTR, SIMPLE_DATACOUNT, SYNC_PNTR
    //     .WRITE_WIDTH(72)                   // 4, 9, 18, 36, 72
    //   )
    //   FIFO36E2_inst (
    //     // Cascade Signals outputs: Multi-FIFO cascade signals
    //     .CASDOUT(),              // 64-bit output: Data cascade output bus
    //     .CASDOUTP(),             // 8-bit output: Parity data cascade output bus
    //     .CASNXTEMPTY(),          // 1-bit output: Cascade next empty
    //     .CASPRVRDEN(),           // 1-bit output: Cascade previous read enable
    //     // ECC Signals outputs: Error Correction Circuitry ports
    //     .DBITERR(),              // 1-bit output: Double bit error status
    //     .ECCPARITY(),            // 8-bit output: Generated error correction parity
    //     .SBITERR(),              // 1-bit output: Single bit error status
    //     // Read Data outputs: Read output data
    //     .DOUT(tmp[i]),         // 64-bit output: FIFO data output bus
    //     .DOUTP(),                // 8-bit output: FIFO parity output bus.
    //     // Status outputs: Flags and other FIFO status outputs
    //     .EMPTY(),                // 1-bit output: Empty
    //     .FULL(),                 // 1-bit output: Full
    //     .PROGEMPTY(),            // 1-bit output: Programmable empty
    //     .PROGFULL(),             // 1-bit output: Programmable full
    //     .RDCOUNT(),              // 14-bit output: Read count
    //     .RDERR(),                // 1-bit output: Read error
    //     .RDRSTBUSY(),            // 1-bit output: Reset busy (sync to RDCLK)
    //     .WRCOUNT(),              // 14-bit output: Write count
    //     .WRERR(),                // 1-bit output: Write Error
    //     .WRRSTBUSY(),            // 1-bit output: Reset busy (sync to WRCLK)
    //     // Cascade Signals inputs: Multi-FIFO cascade signals
    //     .CASDIN(),               // 64-bit input: Data cascade input bus
    //     .CASDINP(),              // 8-bit input: Parity data cascade input bus
    //     .CASDOMUX(),             // 1-bit input: Cascade MUX select input
    //     .CASDOMUXEN(),           // 1-bit input: Enable for cascade MUX select
    //     .CASNXTRDEN(),           // 1-bit input: Cascade next read enable
    //     .CASOREGIMUX(),          // 1-bit input: Cascade output MUX select
    //     .CASOREGIMUXEN(),        // 1-bit input: Cascade output MUX select enable
    //     .CASPRVEMPTY(),          // 1-bit input: Cascade previous empty
    //     // ECC Signals inputs: Error Correction Circuitry ports
    //     .INJECTDBITERR(),        // 1-bit input: Inject a double-bit error
    //     .INJECTSBITERR(),        // 1-bit input: Inject a single bit error
    //     // Read Control Signals inputs: Read clock, enable and reset input signals
    //     .RDCLK(fake_clock),   // 1-bit input: Read clock
    //     .RDEN(1'b0),             // 1-bit input: Read enable
    //     .REGCE(1'b0),            // 1-bit input: Output register clock enable
    //     .RSTREG(1'b0),           // 1-bit input: Output register reset
    //     .SLEEP(1'b0),            // 1-bit input: Sleep Mode
    //     // Write Control Signals inputs: Write clock and enable input signals
    //     .RST(1'b0),              // 1-bit input: Reset
    //     .WRCLK(fake_clock),   // 1-bit input: Write clock
    //     .WREN(1'b0),             // 1-bit input: Write enable
    //     // Write Data inputs: Write input data
    //     .DIN(tmp[i]),            // 64-bit input: FIFO data input bus
    //     .DINP()                  // 8-bit input: FIFO parity input bus
    //   );

    end
  endgenerate

endmodule
