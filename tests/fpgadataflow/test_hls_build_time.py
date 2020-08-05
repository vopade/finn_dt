import pytest
from finn.util.basic import make_build_dir
from finn.util.create import hls_random_mlp_maker
from finn.core.datatype import DataType
from finn.transformation.fpgadataflow.prepare_ip import PrepareIP
from finn.transformation.fpgadataflow.hlssynth_ip import HLSSynthIP
from finn.custom_op.registry import getCustomOp
from finn.transformation.general import GiveUniqueNodeNames
import time
import shutil


@pytest.mark.parametrize("pe", [1, 100])
@pytest.mark.parametrize("simd", [1, 100])
@pytest.mark.parametrize("mw", [100])
@pytest.mark.parametrize("mh", [100])
@pytest.mark.parametrize("idt", [DataType.BIPOLAR])
@pytest.mark.parametrize("wdt", [DataType.BIPOLAR])
@pytest.mark.parametrize("act", [DataType.BIPOLAR])
@pytest.mark.parametrize("mem_mode", ["const", "decoupled"])
@pytest.mark.parametrize("clk_ns", [10, 5])
@pytest.mark.slow
@pytest.mark.vivado
def test_hls_build_time(pe, simd, mw, mh, idt, wdt, act, mem_mode, clk_ns):
    cfg_name = ""
    for (k, v) in locals().items():
        cfg_name += str(k) + "_" + str(v) + "_"
    build_dir = make_build_dir(prefix=cfg_name)
    layer_spec = {
        "idt": idt,
        "wdt": wdt,
        "act": act,
        "mw": mw,
        "mh": mh,
        "pe": pe,
        "simd": simd,
    }
    model = hls_random_mlp_maker([layer_spec])
    model = model.transform(GiveUniqueNodeNames())
    getCustomOp(model.graph.node[0]).set_nodeattr("mem_mode", mem_mode)

    start_time = time.time()
    fpga_part = "xc7z020clg400-1"
    model = model.transform(PrepareIP(fpga_part, clk_ns))
    model = model.transform(HLSSynthIP())
    end_time = time.time()
    model.save(build_dir + "/model.onnx")
    code_gen_dir_ipgen = getCustomOp(model.graph.node[0]).get_nodeattr(
        "code_gen_dir_ipgen"
    )
    shutil.move(code_gen_dir_ipgen, build_dir)

    ret = "%s took %f seconds" % (cfg_name, end_time - start_time)
    with open(build_dir + "/../runtime.txt", "a") as f:
        f.write(ret + "\n")
