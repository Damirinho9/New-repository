# Variant 6 "Фотореле" - canonical mapping
Original drawing: variant 6, printed p.49. This mapping is the only source graph used by Phase A.

|Pos|Ref|Part/value|Connections|
|---:|---|---|---|
|1|R1|4.7 MOhm|U_CTRL-N_R1|
|2|R2|47 kOhm|N_R1-SENS|
|3|VD1|ФД320|A=COM, K=SENS|
|4|C1|К50-35|SENS-COM; capacitance absent in source|
|5|C2|К73|U_CTRL-COM; capacitance absent in source|
|6|VT1|КП501А|SENS/T1, G=COM|
|7|R3|330 Ohm|G12-COM|
|8|R4|10 kOhm|U_CTRL-T1|
|9|VT2|КП501А|T1/T2, G=COM|
|10|VD2|КС512А|A=COM,K=U_CTRL|
|11|R5|5.1 kOhm|U_CTRL-T2|
|12|VT3|КП707В2|T2/VT3_R6,G=COM|
|13|R6|51 Ohm|VT3_R6-DRV|
|14|HL1|L383SRWT|A=LED_A,K=U_CTRL|
|15|VD3|КД243Ж|A=LED_R,K=LED_A|
|16|RU1|FNR-20K391|DRV-COM|
|17|R7|58 kOhm|LED_R-L|
|18|VS1|Т123-250|A=SW,K=COM,G=G1|
|19|R8|56 Ohm|G1-COM|
|20|VD4|КД243Ж|COM-G1; source does not print polarity text|
|21|FU1|32 A|DRV-BR_TOP|
|22|VD6|RB154|BR_TOP,COM,G1,G2; +,-,~ labels absent|
|23|VD5|КД243Ж|A=SW,K=G2|
|24|R9|56 Ohm|G2-SW|
|25|VS2|Т123-250|A=COM,K=SW,G=G2|
|26|C3|К73|L-COM; capacitance absent in source|
|27|FU2|32 A|COM-N|
|-|XP1|МРН-5Ш|external SW/L(load)/L(mains)/N + case contact|

Only source ambiguities allowed: D/S of VT1-VT3 and RB154 terminal roles. Simulation values C1=0.47uF, C2=0.1uF, C3=0.047uF are declared simulation assumptions, not source nominal values.
Preferred physical assignment to test first: VT1 D=T1 S=SENS; VT2 D=T2 S=T1; VT3 D=VT3_R6 S=T2; RB154 V+=COM V-=BR_TOP AC1=G1 AC2=G2.
