set top fifo_gauge
create_project -force -part xc7z020clg400-1 $top $top.vivado
read_verilog -sv $top.sv

set simset [current_fileset -simset]
add_files -fileset $simset ${top}_tb.sv
set_property top ${top}_tb -objects $simset
set_property xsim.simulate.runtime         all  -objects $simset
set_property xsim.simulate.log_all_signals true -objects $simset
launch_simulation
