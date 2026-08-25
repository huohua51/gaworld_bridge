# EXP-GM-05b Fixed-draft review stage

- repeats：[0, 1, 2]，n=54
- 门：review_has_value_fill_repeats
- ReviewStageMultiAgentBenefit：0.5
- ReviewDeliveryValue：0.5
- FalsePositiveRevisionRate：0.3333
- TrueRevisionRate：1.0
- VerifiedPatchAdoptionRate（含 Drop）：0.6667
- VerifiedPatchAdoptionRate（Multi 干预）：1.0
- 补重复：True；开 04f：False；开 05c：True

| instance | track | variant | valid | FullPass | first_error |
|---|---|---|---|---|---|
| gm05b_aid_elig_001_control_single_r0 | single | control | True | 0 | false_positive_revision |
| gm05b_aid_elig_001_control_multi_r0 | multi | control | True | 1 | none |
| gm05b_aid_elig_001_control_drop_r0 | drop | control | True | 1 | none |
| gm05b_aid_elig_001_intervention_single_r0 | single | intervention | True | 1 | none |
| gm05b_aid_elig_001_intervention_multi_r0 | multi | intervention | True | 1 | none |
| gm05b_aid_elig_001_intervention_drop_r0 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_hours_cert_001_control_single_r0 | single | control | True | 0 | false_positive_revision |
| gm05b_hours_cert_001_control_multi_r0 | multi | control | True | 1 | none |
| gm05b_hours_cert_001_control_drop_r0 | drop | control | True | 1 | none |
| gm05b_hours_cert_001_intervention_single_r0 | single | intervention | True | 1 | none |
| gm05b_hours_cert_001_intervention_multi_r0 | multi | intervention | True | 1 | none |
| gm05b_hours_cert_001_intervention_drop_r0 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_route_closed_001_control_single_r0 | single | control | True | 0 | false_positive_revision |
| gm05b_route_closed_001_control_multi_r0 | multi | control | True | 1 | none |
| gm05b_route_closed_001_control_drop_r0 | drop | control | True | 1 | none |
| gm05b_route_closed_001_intervention_single_r0 | single | intervention | True | 1 | none |
| gm05b_route_closed_001_intervention_multi_r0 | multi | intervention | True | 1 | none |
| gm05b_route_closed_001_intervention_drop_r0 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_aid_elig_001_control_single_r1 | single | control | True | 0 | false_positive_revision |
| gm05b_aid_elig_001_control_multi_r1 | multi | control | True | 1 | none |
| gm05b_aid_elig_001_control_drop_r1 | drop | control | True | 1 | none |
| gm05b_aid_elig_001_intervention_single_r1 | single | intervention | True | 1 | none |
| gm05b_aid_elig_001_intervention_multi_r1 | multi | intervention | True | 1 | none |
| gm05b_aid_elig_001_intervention_drop_r1 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_hours_cert_001_control_single_r1 | single | control | True | 0 | false_positive_revision |
| gm05b_hours_cert_001_control_multi_r1 | multi | control | True | 1 | none |
| gm05b_hours_cert_001_control_drop_r1 | drop | control | True | 1 | none |
| gm05b_hours_cert_001_intervention_single_r1 | single | intervention | True | 1 | none |
| gm05b_hours_cert_001_intervention_multi_r1 | multi | intervention | True | 1 | none |
| gm05b_hours_cert_001_intervention_drop_r1 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_route_closed_001_control_single_r1 | single | control | True | 0 | false_positive_revision |
| gm05b_route_closed_001_control_multi_r1 | multi | control | True | 1 | none |
| gm05b_route_closed_001_control_drop_r1 | drop | control | True | 1 | none |
| gm05b_route_closed_001_intervention_single_r1 | single | intervention | True | 1 | none |
| gm05b_route_closed_001_intervention_multi_r1 | multi | intervention | True | 1 | none |
| gm05b_route_closed_001_intervention_drop_r1 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_aid_elig_001_control_single_r2 | single | control | True | 0 | false_positive_revision |
| gm05b_aid_elig_001_control_multi_r2 | multi | control | True | 1 | none |
| gm05b_aid_elig_001_control_drop_r2 | drop | control | True | 1 | none |
| gm05b_aid_elig_001_intervention_single_r2 | single | intervention | True | 1 | none |
| gm05b_aid_elig_001_intervention_multi_r2 | multi | intervention | True | 1 | none |
| gm05b_aid_elig_001_intervention_drop_r2 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_hours_cert_001_control_single_r2 | single | control | True | 0 | false_positive_revision |
| gm05b_hours_cert_001_control_multi_r2 | multi | control | True | 1 | none |
| gm05b_hours_cert_001_control_drop_r2 | drop | control | True | 1 | none |
| gm05b_hours_cert_001_intervention_single_r2 | single | intervention | True | 1 | none |
| gm05b_hours_cert_001_intervention_multi_r2 | multi | intervention | True | 1 | none |
| gm05b_hours_cert_001_intervention_drop_r2 | drop | intervention | True | 0 | review_not_delivered |
| gm05b_route_closed_001_control_single_r2 | single | control | True | 0 | false_positive_revision |
| gm05b_route_closed_001_control_multi_r2 | multi | control | True | 1 | none |
| gm05b_route_closed_001_control_drop_r2 | drop | control | True | 1 | none |
| gm05b_route_closed_001_intervention_single_r2 | single | intervention | True | 1 | none |
| gm05b_route_closed_001_intervention_multi_r2 | multi | intervention | True | 1 | none |
| gm05b_route_closed_001_intervention_drop_r2 | drop | intervention | True | 0 | review_not_delivered |
