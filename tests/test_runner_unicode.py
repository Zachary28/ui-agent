from midscene_ui_agent.infrastructure.execution.runner import CommandRunner, CommandSpec


def test_runner_decodes_non_utf8_output_without_crashing(tmp_path):
    spec = CommandSpec(["python", "-c", "import sys; sys.stdout.buffer.write(bytes([0xff]))"], cwd=str(tmp_path))
    result = CommandRunner(tmp_path / "artifacts").run(spec, run_id="r", event_id="e")
    assert result.returncode == 0 and isinstance(result.stdout, str)
