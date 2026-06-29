@echo off
REM S4 Vivado P&R driver: route the integrated core_top on xc7a35tcsg324-1.
call "E:\AMD\2026.1\Vivado\settings64.bat"
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"
echo === VIVADO PnR core_top ===
call vivado -mode batch -source core_top_pnr.tcl -log core_top_vivado.log -nojournal || exit /b 1
echo === DONE ===
