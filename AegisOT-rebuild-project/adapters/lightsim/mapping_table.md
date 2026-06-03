# DNP3 Mapping Table

| Control Meaning    | DNP3 Type | DNP3 Index | Policy Point       | Operation | LightSim Value |
|--------------------|-----------|------------|--------------------|-----------|----------------|
| Pump Start/Stop    | BO        | 1          | pump_1_startstop   | start     | ON             |
| Pump Start/Stop    | BO        | 1          | pump_1_startstop   | stop      | OFF            |
| Breaker Control    | BO        | 2          | breaker_status_1   | operate   | ON             |
| Breaker Control    | BO        | 2          | breaker_status_1   | release   | OFF            |
| Tank Level (read)  | AI        | 1          | tank_level_1       | read      | (value)        |
| Voltage (read)     | AI        | 2          | voltage_reading_1  | read      | (value)        |
