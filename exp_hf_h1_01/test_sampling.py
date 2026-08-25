from __future__ import annotations

import json
from pathlib import Path

import yaml

from exp_hf_h1_01.extract_stimuli import OUT, extract, planned_cells
from exp_hf_h1_01.anonymize import rater_view


def test_eighteen_mechanical_cells():
    cells = planned_cells()
    assert len(cells) == 18
    constructs = {c[0] for c in cells}
    assert constructs == {"T3", "I1", "L1"}
    assert all(v in {"control", "intervention"} for _, _, v in cells)


def test_extract_full_tracks_only():
    payload = extract()
    assert payload["n_agent"] == 18
    assert payload["manual_best_case_selection"] is False
    tracks = {c["track"] for c in payload["cells"]}
    assert tracks <= {"multi", "full"}
    assert "drop" not in tracks
    assert payload["c1_included"] is False
    ids = [c["stimulus_id"] for c in payload["cells"]]
    assert len(ids) == len(set(ids))
    for cell in payload["cells"]:
        assert cell["H1_role"] == "development_stimulus"
        assert cell["not_future_h1_holdout"] is True
        display = json.loads((OUT / "stimuli" / "display" / f"{cell['stimulus_id']}.json").read_text(encoding="utf-8"))
        assert "source_kind" not in display
        assert "full_pass" not in display
        assert display["variant_code"] in {"A", "B"}
        assert display["turns"]


def test_rater_view_strips_source():
    raw = json.loads((OUT / "stimuli" / "agent" / "h1dev-t3-queue-control.json").read_text(encoding="utf-8"))
    view = rater_view(raw)
    assert "source_kind" not in view
    assert "GLM" not in json.dumps(view)


def test_sampling_file_forbids_cherry_pick():
    sampling = yaml.safe_load(Path(__file__).resolve().parent.joinpath("SAMPLING.yaml").read_text(encoding="utf-8"))
    assert sampling["manual_best_case_selection"] == "prohibited"
    assert "C1" in sampling["exclude_constructs"]
