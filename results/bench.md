| family | harness | success | cost / 1k tasks (USD) | tokens | calls | p50 s | p95 s | agents | failures |
|---|---|---|---|---|---|---|---|---|---|
| simple | single | 0.975 | 0.428 | 2419 | 3.1 | 2.50 | 3.25 | 1 | wrong_arg 5 |
| simple | planner | 0.945 | 0.446 | 2240 | 5.2 | 4.19 | 4.93 | 3 | handoff_loss 6, wrong_arg 3, bad_plan 2 |
| simple | handoff | 0.985 | 0.269 | 1361 | 3.1 | 2.47 | 3.21 | 1 | wrong_arg 3 |
| deep | single | 0.840 | 1.851 | 11136 | 9.5 | 7.11 | 8.65 | 1 | wrong_arg 32 |
| deep | planner | 0.770 | 1.633 | 8844 | 11.6 | 10.90 | 12.41 | 3 | wrong_arg 30, bad_plan 11, handoff_loss 5 |
| deep | handoff | 0.815 | 1.374 | 7644 | 11.6 | 8.71 | 10.21 | 3 | wrong_arg 26, handoff_loss 11 |
| wide | single | 0.775 | 1.852 | 11145 | 9.5 | 7.11 | 8.65 | 1 | wrong_arg 45 |
| wide | planner | 0.685 | 1.456 | 6800 | 18.9 | 6.11 | 6.86 | 10 | handoff_loss 37, wrong_arg 20, bad_plan 6 |
| wide | handoff | 0.645 | 1.394 | 7772 | 11.9 | 9.22 | 10.47 | 3 | handoff_loss 42, wrong_arg 29 |
| mixed | single | 0.875 | 1.566 | 9361 | 8.5 | 6.33 | 7.86 | 1 | wrong_arg 25 |
| mixed | planner | 0.845 | 1.161 | 5788 | 11.6 | 7.49 | 8.98 | 4 | wrong_arg 14, bad_plan 11, handoff_loss 6 |
| mixed | handoff | 0.835 | 1.193 | 6572 | 10.6 | 7.95 | 9.45 | 3 | wrong_arg 18, handoff_loss 15 |

| param | value | family | single | planner | handoff |
|---|---|---|---|---|---|
| p_wrong_per_1k_ctx | 0.0 | deep | 0.945 | 0.880 | 0.930 |
| p_wrong_per_1k_ctx | 0.0 | wide | 0.900 | 0.620 | 0.655 |
| p_wrong_per_1k_ctx | 0.006 | deep | 0.900 | 0.845 | 0.915 |
| p_wrong_per_1k_ctx | 0.006 | wide | 0.850 | 0.620 | 0.630 |
| p_wrong_per_1k_ctx | 0.012 | deep | 0.845 | 0.810 | 0.875 |
| p_wrong_per_1k_ctx | 0.012 | wide | 0.805 | 0.610 | 0.615 |
| p_wrong_per_1k_ctx | 0.024 | deep | 0.765 | 0.765 | 0.835 |
| p_wrong_per_1k_ctx | 0.024 | wide | 0.725 | 0.580 | 0.580 |
| p_wrong_per_1k_ctx | 0.048 | deep | 0.605 | 0.675 | 0.755 |
| p_wrong_per_1k_ctx | 0.048 | wide | 0.550 | 0.550 | 0.530 |
| p_handoff_loss | 0.0 | deep | 0.845 | 0.835 | 0.900 |
| p_handoff_loss | 0.0 | wide | 0.805 | 0.880 | 0.865 |
| p_handoff_loss | 0.04 | deep | 0.845 | 0.825 | 0.890 |
| p_handoff_loss | 0.04 | wide | 0.805 | 0.740 | 0.710 |
| p_handoff_loss | 0.08 | deep | 0.845 | 0.810 | 0.875 |
| p_handoff_loss | 0.08 | wide | 0.805 | 0.610 | 0.615 |
| p_handoff_loss | 0.16 | deep | 0.845 | 0.785 | 0.820 |
| p_handoff_loss | 0.16 | wide | 0.805 | 0.510 | 0.500 |
