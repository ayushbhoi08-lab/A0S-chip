@echo off
REM ============================================================================
REM Ansh-108 Path A -- S9 host<->RTL co-sim, full 2-leg gate. Run from anywhere.
REM   Leg 1: cosim_s9.py  -> cosim_vectors.txt + cosim_golden.txt (REAL host path)
REM   Leg 2: iverilog -g2012 core_top + 9 submodules + tb_cosim_s9.v -> vvp
REM          -> cosim_rtl_out.txt ; check_cosim_s9.py compares RTL vs golden.
REM ============================================================================
setlocal
set ART=D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts
set IV=C:\iverilog\bin
cd /d "%ART%"

echo ===== LEG 1: cosim_s9.py (real S6/S7/S8 host path -> vectors + golden) =====
python cosim_s9.py
if errorlevel 1 (echo DRIVER FAILED & exit /b 1)

echo ===== iverilog -g2012 (core_top + 9 submodules + tb_cosim_s9.v) =====
call "%IV%\iverilog" -g2012 -o tb_cosim_s9.vvp core_top.v opcode_decode.v result_mode.v rns_reduce.v tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v rns_verify.v fold_hash.v tb_cosim_s9.v
if errorlevel 1 (echo IVERILOG FAILED & exit /b 1)

echo ===== LEG 2: vvp (drive RTL core_top, write cosim_rtl_out.txt) =====
call "%IV%\vvp" tb_cosim_s9.vvp
if errorlevel 1 (echo VVP FAILED & exit /b 1)

echo ===== GATE: check_cosim_s9.py (RTL vs golden) =====
python check_cosim_s9.py
echo CHECK_EXIT=%errorlevel%
echo ===== DONE =====
endlocal
