module lutram_array();

  parameter G_SIZE = 4;

  wire [G_SIZE-1 : 0] lutram_out;

  genvar i;
  generate
    for (i=0; i<G_SIZE; i=i+1) begin : lutram_gen
      (* DONT_TOUCH = "yes" *)
      RAM64X1S #(
        .INIT(64'h0000000000000000)
      )
      lutram_inst (
        .O(lutram_out[i]),
        .A0(1'b0),
        .A1(1'b0),
        .A2(1'b0),
        .A3(1'b0),
        .A4(1'b0),
        .A5(1'b0),
        .D(lutram_out[i]),
        .WCLK(1'b0),
        .WE(1'b0)
      );
    end
  endgenerate

endmodule
