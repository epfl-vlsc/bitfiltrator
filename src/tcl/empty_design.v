module empty_design();

  (* DONT_TOUCH = "yes" *)
  FDRE #(
    .INIT(1'b0),
    .IS_C_INVERTED(1'b0),
    .IS_D_INVERTED(1'b0),
    .IS_R_INVERTED(1'b0)
  )
  FDRE_inst (
    .Q(),
    .C(1'b0),
    .CE(1'b1), // Clock-Enable must be active otherwise no entry is generated in the logic location file.
    .D(1'b0),
    .R(1'b0)
  );

endmodule
