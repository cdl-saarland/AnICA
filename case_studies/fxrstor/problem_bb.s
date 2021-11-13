.intel_syntax noprefix
vpsubq xmm5, xmm7, xmmword ptr [rbx + 0x40]
vunpckhpd ymm3, ymm2, ymm7
cmp al, 0x0
fxrstor64 [rbx + 0x40]
