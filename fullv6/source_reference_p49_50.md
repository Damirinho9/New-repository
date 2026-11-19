# Variant 6, original printed pages 49-50 (PDF pages 44-45)
The crossing between the bridge bottom-to-CASE line and the mains return line has no junction dot. Keep CASE (=simulation 0) and N_INT separate. RREF 1 GOhm is simulation-only, not a source connection. XP1 pin numbering is not given; P5 unassigned. R1 appears as a resistor with a third connection to the same top rail; use its effective resistance as an explicitly documented simplification. Capacitances unspecified. D/S mapping, bridge pin identification and VD4 polarity unspecified.
|Pos|Ref|Source part|Source nets (pin assignments if marked)|
|---|---|---|---|
|1|R1|MLT 4.7 MOhm|U_CTRL,N_R1|
|2|R2|MLT 47 kOhm|N_R1,SENS|
|3|VD1|FD320|A=CASE,K=SENS|
|4|C1|K50-35|SENS,CASE|
|5|C2|K73|U_CTRL,CASE; + at U_CTRL|
|6|VT1|KP501A|SENS,T1,G=G12|
|7|R3|330 Ohm|G12,CASE|
|8|R4|10 kOhm|U_CTRL,T1|
|9|VT2|KP501A|T1,T2,G=G12|
|10|VD2|KS512A|A=CASE,K=U_CTRL|
|11|R5|5.1 kOhm|U_CTRL,T2|
|12|VT3|KP707V2|T2,VT3_R6,G=CASE|
|13|R6|51 Ohm|VT3_R6,DRV|
|14|HL1|L383SRWT|A=LED_A,K=U_CTRL|
|15|VD3|KD243Zh|A=LED_R,K=LED_A|
|16|RU1|FNR-20K391|DRV,CASE; normal-state 10 MOhm approximation only|
|17|R7|58 kOhm|LED_R,L|
|18|VS1|T123-250|A=SW,K=N_INT,G=G18|
|19|R8|56 Ohm|G18,N_INT|
|20|VD4|KD243Zh|G18,N_INT; polarity not given|
|21|FU1|103 32A|DRV,BR_TOP|
|22|VD6|RB154|BR_TOP,CASE,G18,G25; pin labels absent|
|23|VD5|KD243Zh|A=SW,K=G25|
|24|R9|56 Ohm|G25,SW|
|25|VS2|T123-250|A=N_INT,K=SW,G=G25|
|26|C3|K73|L,N_INT|
|27|FU2|103 32A|N_INT,N|
|XP1|XP1|MRN-5Sh|4 external connections SW,L,L,N; fifth not specified|
C1=470nF, C2=100nF, C3=47nF are simulation assumptions, not source ratings. RLOAD=1kOhm, 220V rms / 50Hz. An exact T123-250, ZVN2120, KP707V2 manufacturer SPICE model has not been verified. Functional NI SCR modified only to refer the gate detector to its cathode; MOSFET model parameters are approximations, not a certified fit. The model must not be used as a hardware construction or mains safety design.
