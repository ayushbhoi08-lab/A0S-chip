@echo off
REM S3 Vivado P&R driver: route rns_verify and fold_hash on xc7a35tcsg324-1.
call "E:\AMD\2026.1\Vivado\settings64.bat"
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"
echo === VIVADO PnR rns_verify ===
call vivado -mode batch -source rns_verify_pnr.tcl -log rns_verify_vivado.log -nojournal || exit /b 1
echo === VIVADO PnR fold_hash ===
call vivado -mode batch -source fold_hash_pnr.tcl -log fold_hash_vivado.log -nojournal || exit /b 1
echo === DONE ===
