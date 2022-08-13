module lut_array();

  parameter G_SIZE = 4;

  wire [G_SIZE-1 : 0] lut_out;

  genvar i;
  generate
    for (i=0; i<G_SIZE; i=i+1) begin : lut_gen
      (* DONT_TOUCH = "yes" *)
      LUT6 #(
        .INIT(64'h0000000000000000)
      )
      lut6_inst (
        .O(lut_out[i]),
        .I0(lut_out[i]),
        .I1(lut_out[i]),
        .I2(lut_out[i]),
        .I3(lut_out[i]),
        .I4(lut_out[i]),
        .I5(lut_out[i])
      );
    end
  endgenerate

endmodule
