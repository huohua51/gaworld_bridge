# T4 GLM-5.2 control/full consistency pilot

Status: completed exploratory live-model pilot; not ranking eligible.

## Frozen design

- Preregistration: `T4-CONTROL-CONSISTENCY-GLM52-v1`
- Preregistration commit: `03f1c8f`
- Runner commit: `44aa027`
- T4 scorer: `model-pilot-t4-scorer-v2` (`15cd075`)
- Provider/model: `paratera_glm / GLM-5.2`
- Inference: `temperature=0`, `thinking=disabled`, `max_tokens=256`
- Matrix: three control/full tasks by three repeats, nine cells
- Logical call budget: 36
- Post-response retries or replacement cells: none

## Results

All nine cells were measurement-valid and all model responses satisfied the
registered JSON contract. The run used 26 of 36 allowed logical calls.

| Task | Source decisions | Exact agreement | Complete-path rate | FullPass rate |
| --- | --- | ---: | ---: | ---: |
| `t4_ferry_closure_001` | `false, false, true` | no | 33.33% | 33.33% |
| `t4_clinic_recall_001` | `true, true, true` | yes | 100% | 100% |
| `t4_shelter_capacity_001` | `false, false, false` | yes | 0% | 0% |

Pooled source-forward, complete-path and FullPass rates were each 44.44%.
The model-contract rate was 100%. Five cells first failed at
`propagation_path_incomplete`; four had no error.

## Interpretation boundary

The source prompt hash was identical across the three repeats within every
task. The result therefore records both a task-surface effect and one case of
same-input decision inconsistency under the provider's nominal zero-temperature
setting. It does not establish cross-model generality, human validity or a
ranking result.

One transient TLS EOF was retried inside the existing HTTP transport for the
same logical model call. The benchmark manifest counts logical calls, not raw
HTTP attempts. No structurally valid response was retried and no failed cell
was replaced.

`CONSISTENCY_MANIFEST.yaml` is the authoritative aggregate. Each run directory
contains its model request/response trace, network trace and v2 cell result.
