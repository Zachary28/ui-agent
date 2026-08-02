"""Typer command-line interface for direct and configured UI automation."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from ..application.services.skills import SkillCatalog
from ..domain.contracts import AutomationRequest, ReferenceImage
from .api import resume_run, run as execute, run_configured

app = typer.Typer()


@app.command("run")
def run_command(
    platform: str | None = typer.Option(None, "--platform"),
    app_name: str | None = typer.Option(None, "--app"),
    task: str | None = typer.Option(None, "--task"),
    environment: str | None = typer.Option(None, "--environment"),
    override: list[str] = typer.Option([], "--override"),
    config_root: Path | None = typer.Option(None, "--config-root"),
    skills_root: Path | None = typer.Option(None, "--skills-root"),
    skills_lock: Path | None = typer.Option(None, "--skills-lock"),
    goal: str | None = typer.Option(None, "--goal"),
    url: str | None = typer.Option(None, "--url"),
    device_id: str | None = typer.Option(None, "--device-id"),
    operation: str = typer.Option("run", "--operation"),
    mode: str | None = typer.Option(None, "--mode"),
    report_dir: str = typer.Option("./artifacts", "--report-dir"),
    project_dir: str | None = typer.Option(None, "--project-dir"),
    vitest_platform: str | None = typer.Option(None, "--vitest-platform"),
    app_uri: str | None = typer.Option(None, "--launch-uri"),
    cdp: str | None = typer.Option(None, "--cdp"),
    bridge: bool = typer.Option(False, "--bridge"),
    wda_host: str | None = typer.Option(None, "--wda-host"),
    wda_port: int | None = typer.Option(None, "--wda-port"),
    raw_command: str | None = typer.Option(None, "--raw-command"),
    raw_method: str | None = typer.Option(None, "--raw-method"),
    raw_endpoint: str | None = typer.Option(None, "--raw-endpoint"),
    locate_json: str | None = typer.Option(None, "--locate-json"),
    deep_think: bool = typer.Option(False, "--deep-think"),
    deep_locate: bool = typer.Option(False, "--deep-locate"),
    resume_id: str | None = typer.Option(None, "--resume"),
    run_id: str | None = typer.Option(None, "--run-id"),
    image: list[str] = typer.Option([], "--image"),
    image_name: list[str] = typer.Option([], "--image-name"),
    convert_http_image2_base64: bool = typer.Option(False, "--convert-http-image2-base64"),
    check_dependencies: bool = typer.Option(False, "--check-dependencies"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        if check_dependencies:
            if platform is None:
                raise ValueError("--platform is required with --check-dependencies")
            from ..infrastructure.config.checks import check_dependencies as check

            typer.echo(json.dumps(check(platform)))
            return
        if len(image) != len(image_name):
            raise ValueError("--image and --image-name must be paired")

        configured = any(value is not None for value in (app_name, task, config_root, environment)) or bool(override)
        target_overrides = {
            key: value
            for key, value in {
                "url": url,
                "device_id": device_id,
                "project_dir": project_dir,
                "vitest_platform": vitest_platform,
                "app_uri": app_uri,
                "cdp": cdp,
                "bridge": bridge,
                "wda_host": wda_host,
                "wda_port": wda_port,
                "convert_http_image2_base64": convert_http_image2_base64,
            }.items()
            if value is not None
        }

        resume_only = resume_id is not None and not any((platform, app_name, task))
        if resume_only:
            result = resume_run(
                resume_id,
                report_dir=report_dir,
                skills_root=skills_root,
                skills_lock=skills_lock,
            )
        elif configured:
            if not (platform and app_name and task):
                raise ValueError("--platform, --app and --task are required for configured runs")
            result = run_configured(
                platform=platform,
                app=app_name,
                task=task,
                environment=environment,
                overrides=override,
                config_root=config_root,
                skills_root=skills_root,
                skills_lock=skills_lock,
                target_overrides=target_overrides,
                resume_id=resume_id,
                mode=mode or "plan",
                operation=operation,
                report_dir=report_dir,
                run_id=run_id,
            )
        elif resume_id is not None:
            result = resume_run(
                resume_id,
                report_dir=report_dir,
                skills_root=skills_root,
                skills_lock=skills_lock,
            )
        else:
            if platform is None or goal is None:
                raise ValueError("--platform and --goal are required for direct runs")
            target_overrides["reference_images"] = [
                ReferenceImage(name=name, source=source) for source, name in zip(image, image_name)
            ]
            locate = json.loads(locate_json) if locate_json else None
            request = AutomationRequest(
                platform=platform,
                target=target_overrides,
                goal=goal,
                operation=operation,
                mode=mode or "plan",
                report_dir=report_dir,
                run_id=run_id,
                raw_command=raw_command,
                raw_method=raw_method,
                raw_endpoint=raw_endpoint,
                locate=locate,
                deep_think=deep_think,
                deep_locate=deep_locate,
            )
            result = execute(request, skills_root=skills_root, skills_lock=skills_lock)

        typer.echo(result.model_dump_json() if json_output else f"{result.status}: {result.run_id}")
        if result.status in {"failed", "resume_invalid"}:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command("vitest")
def vitest(
    operation: str,
    project_dir: str,
    vitest_platform: str,
    goal: str,
    mode: str = "plan",
    report_dir: str = "./artifacts",
    test_name: str | None = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = execute(
        AutomationRequest(
            platform="vitest_e2e",
            target={"project_dir": project_dir, "vitest_platform": vitest_platform},
            goal=goal,
            operation=operation,
            mode=mode,
            report_dir=report_dir,
            test_name=test_name,
        )
    )
    typer.echo(result.model_dump_json() if json_output else f"{result.status}: {result.run_id}")


@app.command("skills")
def skills(action: str, skills_root: str, lock_file: str) -> None:
    catalog = SkillCatalog(skills_root)
    catalog.write_lock(lock_file) if action == "lock" else catalog.verify_lock(lock_file)
    typer.echo("ok")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
