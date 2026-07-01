esptool ^
--chip esp32c3 ^
--baud 460800 ^
erase-flash

esptool ^
--chip esp32c3 ^
--baud 460800 ^
--before default-reset ^
--after hard-reset ^
write-flash -z ^
--flash-mode dio ^
--flash-freq 80m ^
--flash-size 4MB ^
0x0000 ./.pio/build/esp32-c3-devkitm-1/bootloader.bin ^
0x8000 ./.pio/build/esp32-c3-devkitm-1/partitions.bin ^
0xe000 %USERPROFILE%/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin ^
0x10000 .pio/build/esp32-c3-devkitm-1/firmware.bin