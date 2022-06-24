module ff_array();

  parameter G_SIZE = 4;

  wire [G_SIZE-1 : 0] ff_out;

  genvar i;
  generate
    for (i=0; i<G_SIZE; i=i+1) begin : ff_gen
      (* DONT_TOUCH = "yes" *)
      FDRE #(
        .INIT(1'b0),
        .IS_C_INVERTED(1'b0),
        .IS_D_INVERTED(1'b0),
        .IS_R_INVERTED(1'b0)
      )
      ff_inst (
        .Q(ff_out[i]),
        .C(1'b0),
        .CE(1'b0),
        .D(ff_out[i]),
        .R(1'b0)
      );
    end
  endgenerate

endmodule
