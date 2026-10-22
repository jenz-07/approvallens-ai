from benchmarks.generators.verifybench import generate, dataset_hash

def test_generator_deterministic_and_family_grouped():
    a, b = generate(80, 16, 5), generate(80, 16, 5)
    assert dataset_hash(a) == dataset_hash(b)
    split_of = {}
    for c in a:
        assert split_of.setdefault(c["family_id"], c["split"]) == c["split"]
    assert {c["split"] for c in a} >= {"train", "calibration", "test", "test_ood"}

def test_ground_truth_covers_conflicts_and_benign_variation():
    cs = generate(400, 0, 3); labels = [u["label"] for c in cs for u in c["units"].values()]
    assert 0 < sum(labels) < len(labels) * 0.2
    assert any(c["scenario"] == "version_supersede" for c in cs)
