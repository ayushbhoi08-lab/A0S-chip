@echo off
REM S2 P&R driver: route rns_add and rns_sub on xc7a35tcsg324-1 (Vivado 2026.1).
call "E:\AMD\2026.1\Vivado\settings64.bat"
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"
echo === VIVADO P&R rns_add ===
call vivado -mode batch -source rns_add_pnr.tcl -log rns_add_vivado.log -journal rns_add_vivado.jou -nojournal || exit /b 1
echo === VIVADO P&R rns_sub ===
call vivado -mode batch -source rns_sub_pnr.tcl -log rns_sub_vivado.log -journal rns_sub_vivado.jou -nojournal || exit /b 1
echo === DONE ===
