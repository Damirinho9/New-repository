# 7342510 - Stage 4 clean 1C infobase

Target runtime: 1C:Enterprise training 8.3.27.1508 for Windows.

Configuration:
- DB7342510
- XML format 2.20
- CompatibilityMode Version8_3_27
- ManagedApplication run mode

The source order contains no 1C platform, CF, DT or ready infobase. The connected repository also has no 1C release credentials.

The workflow requires repository secret ONEC_TRAINING_URL with a fresh official download URL received from online.1c.ru. The temporary URL is never committed to this public repository.

Acceptance:
1. install official training platform;
2. create clean file infobase and verify 1Cv8.1CD;
3. generate and load minimal configuration;
4. UpdateDBCfg and CheckConfig;
5. launch 1C:Enterprise and keep the process alive during the acceptance window;
6. dump 7342510_stage4_clean.dt;
7. calculate SHA-256 and upload DT, 1Cv8.1CD, XML source and logs.

After ONEC_TRAINING_URL is configured, create or modify onec-7342510/trigger-stage4.txt on branch onec-7342510-base to start the run.
