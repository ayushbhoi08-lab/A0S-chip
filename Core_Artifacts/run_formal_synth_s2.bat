@echo off
REM S2 formal + synth driver (oss-cad-suite). sby = SymbiYosys/boolector BMC proof,
REM yosys synth_xilinx = resource estimate. Run from the artifacts dir.
call C:\oss-cad-suite\environment.bat
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"

echo ===== SBY rns_add =====
call sby -f rns_add.sby
echo SBY_ADD_EXIT=%errorlevel%

echo ===== SBY rns_sub =====
call sby -f rns_sub.sby
echo SBY_SUB_EXIT=%errorlevel%

echo ===== YOSYS synth rns_add =====
call yosys -ql rns_add_synth.log synth_rns_add.ys
echo YOSYS_ADD_EXIT=%errorlevel%

echo ===== YOSYS synth rns_sub =====
call yosys -ql rns_sub_synth.log synth_rns_sub.ys
echo YOSYS_SUB_EXIT=%errorlevel%

echo ===== DONE =====
