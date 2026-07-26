def test_new_public_imports_and_legacy_facades_resolve_to_same_types():
    from midscene_ui_agent.domain.contracts import AutomationRequest as NewRequest
    from midscene_ui_agent.contracts import AutomationRequest as LegacyRequest
    assert NewRequest is LegacyRequest

def test_domain_does_not_import_platform_or_infrastructure_modules():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / 'src/midscene_ui_agent/domain'
    forbidden = ('platforms', 'infrastructure', 'interfaces', 'midscene')
    imports = [node for path in root.rglob('*.py') for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any(any(word in (getattr(node, 'module', '') or '') for word in forbidden) for node in imports)


def test_legacy_adapter_facades_preserve_canonical_identity():
    from midscene_ui_agent.adapters.android import AndroidAdapter as LegacyAndroid
    from midscene_ui_agent.platforms.android.android import AndroidAdapter
    from midscene_ui_agent.adapters.browser import BrowserAdapter as LegacyBrowser
    from midscene_ui_agent.platforms.browser.browser import BrowserAdapter
    from midscene_ui_agent.adapters.base import PlatformAdapter as LegacyBase
    from midscene_ui_agent.platforms.base import PlatformAdapter
    assert LegacyAndroid is AndroidAdapter
    assert LegacyBrowser is BrowserAdapter
    assert LegacyBase is PlatformAdapter


def test_cli_import_and_dependency_check_smoke():
    from typer.testing import CliRunner
    from midscene_ui_agent.interfaces.cli import app
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
