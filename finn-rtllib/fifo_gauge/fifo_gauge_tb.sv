/******************************************************************************
 *  Copyright (c) 2021, Xilinx, Inc.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are met:
 *
 *  1.  Redistributions of source code must retain the above copyright notice,
 *     this list of conditions and the following disclaimer.
 *
 *  2.  Redistributions in binary form must reproduce the above copyright
 *      notice, this list of conditions and the following disclaimer in the
 *      documentation and/or other materials provided with the distribution.
 *
 *  3.  Neither the name of the copyright holder nor the names of its
 *      contributors may be used to endorse or promote products derived from
 *      this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 *  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 *  THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 *  PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
 *  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 *  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 *  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 *  OR BUSINESS INTERRUPTION). HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 *  WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 *  OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
 *  ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * @brief	Testbench for fifo_gauge.
 * @author	Thomas B. Preußer <tpreusse@amd.com>
 *
 *******************************************************************************/
module fifo_gauge_tb;

	localparam int unsigned  N = 1500;
	localparam int unsigned  W = 20;
	typedef  logic [W-1:0]  data_t;

	// Global Control
	logic  clk = 0;
	always #5ns  clk = !clk;
	uwire  rst = 0;

	//-----------------------------------------------------------------------
	// DUT

	// Input Stream
	data_t  idata;
	logic   ivalid;
	uwire   iready;

	// Output Stream
	uwire data_t  odata;
	uwire         ovalid;
	logic         oready;

	fifo_gauge #(.NAME("FIFO GAUGE"), .W(W)) dut (
		.clk, .rst,
		.idata, .ivalid, .iready,
		.odata, .ovalid, .oready
	);

	//-----------------------------------------------------------------------
	// Stimulus
	data_t  Q[$] = {};
	initial begin
		idata  = 'x;
		ivalid =  0;
		@(posedge clk iff !rst);
		repeat(N) begin
			automatic data_t  data = $urandom();
			repeat(3-$clog2(2+$urandom()%6))  @(posedge clk);
			idata  <= data;
			ivalid <= 1;
			Q.push_back(data);
			@(posedge clk);
			idata  <= 'x;
			ivalid <=  0;
		end
	end

	//-----------------------------------------------------------------------
	// Checker
	initial begin
		automatic bit  good = 1;

		oready = 0;
		@(posedge clk iff !rst);
		repeat(N) begin
			repeat(3-$clog2(2+$urandom()%6))  @(posedge clk);
			oready <= 1;
			@(posedge clk iff ovalid);
			assert(Q.size()) else begin
				good = 0;
				$error("Spurious output.");
				$stop;
			end
			assert(odata == Q.pop_front()) else begin
				good = 0;
				$error("Output mismatch.");
				$stop;
			end
			oready <= 0;
		end

		$display("Test %s.", good? "completed SUCCESSfully" : "FAILed");
		$finish;
	end

endmodule : fifo_gauge_tb
