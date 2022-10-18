# Copyright (c) 2020, Xilinx
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of FINN nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import pytest
import numpy as np
from onnx import TensorProto, helper
from pyverilator.util.axi_utils import axilite_read, axilite_write, reset_rtlsim
from qonnx.core.datatype import DataType
from qonnx.core.modelwrapper import ModelWrapper
from qonnx.custom_op.general.multithreshold import multithreshold
from qonnx.custom_op.registry import getCustomOp
from qonnx.transformation.general import GiveUniqueNodeNames
from qonnx.util.basic import gen_finn_dt_tensor

import finn.core.onnx_exec as oxe
from finn.analysis.fpgadataflow.exp_cycles_per_layer import exp_cycles_per_layer
from finn.analysis.fpgadataflow.hls_synth_res_estimation import hls_synth_res_estimation
from finn.core.rtlsim_exec import rtlsim_exec
from finn.transformation.fpgadataflow.compile_cppsim import CompileCppSim
from finn.transformation.fpgadataflow.create_stitched_ip import CreateStitchedIP
from finn.transformation.fpgadataflow.hlssynth_ip import HLSSynthIP
from finn.transformation.fpgadataflow.insert_fifo import InsertFIFO
from finn.transformation.fpgadataflow.prepare_cppsim import PrepareCppSim
from finn.transformation.fpgadataflow.prepare_ip import PrepareIP
from finn.transformation.fpgadataflow.prepare_rtlsim import PrepareRTLSim
from finn.transformation.fpgadataflow.set_exec_mode import SetExecMode

test_fpga_part = "xczu3eg-sbva484-1-e"
target_clk_ns = 5

def sort_thresholds_increasing(thresholds):
    return np.sort(thresholds, axis=1)

def generate_random_threshold_values(input_data_type, num_input_features, num_steps):
    return np.random.randint(input_data_type.min(), input_data_type.max() + 1, (num_input_features, num_steps)).astype(np.float32)

def generate_pe_value(fold, num_input_features):
    if fold == -1:
        fold = num_input_features
    pe = num_input_features // fold
    assert num_input_features % pe == 0
    return pe

# n = batch, c = channel, h = height, w = width of feature map
# Standard = NCHW; FINN = NHWC
# Convert from NCHW to NHWC
def convert_np_array_to_finn_data_layout(data):
    return np.transpose(data, (0, 2, 3, 1))

# n = batch, c = channel, h = height, w = width of feature map
# Standard = NCHW; FINN = NHWC
# Convert from NHWC to NCHW
def convert_np_array_to_standard_data_layout(data):
    return np.transpose(data, (0, 3, 1, 2))

def make_single_thresholding_modelwrapper(
    thresholds, pe, input_data_type, output_data_type, actval, mem_mode, num_input_vecs
):
    NumChannels = thresholds.shape[0]

    inp = helper.make_tensor_value_info(
        "inp", TensorProto.FLOAT, num_input_vecs + [NumChannels]
    )
    outp = helper.make_tensor_value_info(
        "outp", TensorProto.FLOAT, num_input_vecs + [NumChannels]
    )

    node_inp_list = ["inp", "thresh"]

    Thresholding_node = helper.make_node(
        "Thresholding_Binary_Search",
        node_inp_list,
        ["outp"],
        domain="finn.custom_op.fpgadataflow",
        backend="fpgadataflow",
        NumChannels=NumChannels,
        PE=pe,
        numSteps=thresholds.shape[1],
        inputDataType=input_data_type.name,
        weightDataType=input_data_type.name,  # will be set by MinimizeAccumulatorWidth
        outputDataType=output_data_type.name,
        ActVal=actval,
        mem_mode=mem_mode,
        numInputVectors=num_input_vecs,
    )
    graph = helper.make_graph(
        nodes=[Thresholding_node],
        name="thresholding_graph",
        inputs=[inp],
        outputs=[outp],
    )

    model = helper.make_model(graph, producer_name="thresholding-model")
    model = ModelWrapper(model)

    model.set_tensor_datatype("inp", input_data_type)
    model.set_tensor_datatype("outp", output_data_type)

    model.set_tensor_datatype("thresh", input_data_type)
    model.set_initializer("thresh", thresholds)
    return model

@pytest.mark.wip
def test_fpgadataflow_thresholding_binary_search_wip():
    act = DataType["INT4"]
    input_data_type = DataType["INT16"]
    fold = -1
    num_input_features = 16
    mem_mode = "const"

    # Handle inputs to the test
    pe = generate_pe_value(fold, num_input_features)
    num_steps = act.get_num_possible_values() - 1

    # Generate random, non-decreasing thresholds
    thresholds = generate_random_threshold_values(input_data_type, num_input_features, num_steps)
    thresholds = sort_thresholds_increasing(thresholds)

    # Other non-input parameters
    num_input_vecs = [1, 2, 2]
    output_data_type = act
    actval = output_data_type.min()

    # Generate model from input parameters to the test
    model = make_single_thresholding_modelwrapper(
        thresholds, pe, input_data_type, output_data_type, actval, mem_mode, num_input_vecs
    )

    x = gen_finn_dt_tensor(input_data_type, tuple(num_input_vecs + [num_input_features]))
    input_dict = {"inp": x}

    model = model.transform(InsertFIFO(True))
    model = model.transform(GiveUniqueNodeNames())
    model = model.transform(PrepareIP(test_fpga_part, target_clk_ns))
    model = model.transform(HLSSynthIP())
    model = model.transform(CreateStitchedIP(test_fpga_part, target_clk_ns))
    model.set_metadata_prop("exec_mode", "rtlsim")

    rtlsim_exec(model, input_dict)
    assert True == False, "Should not get this far"
