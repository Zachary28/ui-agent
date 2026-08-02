def test_evidence_collector_uses_stable_operation_id(tmp_path) -> None:
    from midscene_ui_agent.infrastructure.evidence.collector import EvidenceCollector

    paths = []

    def capture(operation, phase, path):
        paths.append(path)
        path.write_bytes(b"evidence")
        return True

    collector = EvidenceCollector(tmp_path, capture=capture)

    ref = collector.capture_before("switch_episode", operation_id="tick-7:switch_episode")

    assert ref is not None
    assert paths[0].name == "tick-7-switch_episode-switch_episode-before.jpeg"
