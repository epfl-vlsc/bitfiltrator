module ring_reg();

  parameter G_SIZE = 4;

  wire [G_SIZE : 0] tmp;

  assign tmp[0] = tmp[G_SIZE];

  genvar i;
  generate
    for (i=0; i<G_SIZE; i=i+1) begin : FDRE_gen
      (* DONT_TOUCH = "yes" *)
      FDRE #(
        .INIT(1'b0),
        .IS_C_INVERTED(1'b0),
        .IS_D_INVERTED(1'b0),
        .IS_R_INVERTED(1'b0)
      )
      FDRE_inst (
        .Q(tmp[i+1]),
        .C(1'b0),
        .CE(1'b0),
        .D(tmp[i]),
        .R(1'b0)
      );
    end
  endgenerate

endmodule
