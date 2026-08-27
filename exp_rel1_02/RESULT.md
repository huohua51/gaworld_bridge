# EXP-GM-REL1-02 registered result

- Model/calls: GLM-5.2, 30/30
- Coverage: 4/6
- FullPass among measurable cells: 1/4
- Formation correct among measurable cells: 1/4
- Latest-binding update correct among measurable cells: 4/4
- Update action platform-bound among measurable cells: 4/4
- Registered gate: `measurement_invalid`

Both ferry cells were invalid because Observer returned `{"signals":[]}`.
In other formation failures, the model often cited only the second history row
instead of counting both supporting rows; one cell also selected the wrong
source. The shared formation/update prompt likely let the latest-row rule bleed
into formation. Update behavior itself was correct in every measurable cell.

REL1-v2 remains frozen. AP-REL1-01/02/03 do not close under the registered
all-or-nothing gate; a new-number regression must separate the two phase
instructions and explicitly measure per-source formation counts.
