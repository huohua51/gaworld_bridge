# EXP-GM-REL1-02

Status: completed, registered live measurement gate failed.

This new-number regression repairs source selection, latest-row override, and
Dispatcher evidence binding without adding an automatic reliability updater.
The model still selects the source and business value; the platform owns only
transport identifiers and registered submission metadata.

The frozen GLM-5.2 run is stored in `output/exp_gm_rel1_02_20260827`.
Coverage was 4/6 because the ferry Observer returned an empty signal list in
both variants. Among the four measurable cells, latest-row update and bound
update action were 4/4, while formation was 1/4: several responses cited only
the second formation row, and one selected the wrong source. The result is
preserved with gate `measurement_invalid`; no action item closes from v2.
