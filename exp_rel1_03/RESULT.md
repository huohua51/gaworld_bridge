# EXP-GM-REL1-03 result

Run date: 2026-08-27  
Model: GLM-5.2 through Paratera  
Registration: `REL1-PHASE-SEPARATED-GLM52-v3`  
Registration SHA-256: `f689a0787231be92aba84702a9fc97ad5a2147c1fa2be4a0adbbf174ab4617e2`  
Frozen preregistration commit: `f4ae06f`  
Gate: `measurement_invalid`

The run used exactly 30/30 permitted calls. Five of six cells were measurable,
and all five were FullPass. Their observer relay, formation counts, formation
source, latest-binding update source, and both platform-bound actions were all
correct.

The single invalid cell was
`rel1_v3_rel1_03_alpine_road_001_control_full_s0`. Its update call correctly
returned `pass_blocked` and cited only `ar-c-03`, but returned integer `1` for
both `trusted_source_id` and `other_source_id`. The registered validator
rejected the source pair. No retry was allowed or performed.

Because registered coverage was 0.8333 rather than 1.0, AP-REL1-01,
AP-REL1-02, and AP-REL1-03 remain formally open. The result is evidence that
the v2 formation/update contamination and observer omission did not recur in
the measurable cells, but it is not a passing implementation regression and
does not overwrite either earlier REL1 result.
