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
 * @brief	AXI Stream FIFO for gauging depth without backpressure assertion.
 * @author	Thomas B. Preußer <tpreusse@amd.com>
 *
 *******************************************************************************/
module fifo_gauge #(
	parameter     NAME,
	int unsigned  W
)(
	input	logic  clk,
	input	logic  rst,

	input	logic [W-1:0]  idata,
	input	logic          ivalid,
	output	logic          iready,

	output	logic [W-1:0]  odata,
	output	logic          ovalid,
	input	logic          oready
);

	logic [W-1:0]  Queue[$] = {};
	int            MaxDepth = 0;
	logic [W-1:0]  OData  = 'x;
	logic          OValid =  0;
	always_ff @(posedge clk) begin
		if(rst) begin
			Queue    <= {};
			MaxDepth <= 0;
			OData  <= 'x;
			OValid <=  0;
		end
		else begin
			// Always enqueue new input as it becomes available & track queue depth
			if(ivalid) begin
				automatic int  s;
				Queue.push_back(idata);

				s = Queue.size();
				if(s > MaxDepth) begin
					MaxDepth <= s;
					$display("[%s] DEPTH -> %0d", NAME, s);
				end
			end

			// Update output if empty or taken
			if(oready || !OValid) begin
				if(Queue.size()) begin
					OData  <= Queue.pop_front();
					OValid <= 1;
				end
				else begin
					OData  <= 'x;
					OValid <= 0;
				end
			end
		end
	end
	assign	iready = 1;		// Growing Queue instead of applying backpressure
	assign	odata  = OData;
	assign	ovalid = OValid;

	final begin
		$display("[%s] Final DEPTH=%0d", NAME, MaxDepth);
	end

endmodule : fifo_gauge
