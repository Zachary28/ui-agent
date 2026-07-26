import json
import typer
from ..domain.contracts import AutomationRequest, ReferenceImage
from .api import run as execute
from ..application.services.skills import SkillCatalog
app=typer.Typer()
@app.command()
def run(platform:str=typer.Option(...,"--platform"), goal:str=typer.Option(...,"--goal"), url:str|None=None, device_id:str|None=None, operation:str="run", mode:str="plan", report_dir:str="./artifacts", project_dir:str|None=None, vitest_platform:str|None=None, app_uri:str|None=typer.Option(None,"--launch-uri"), cdp:str|None=None, bridge:bool=False, wda_host:str|None=None, wda_port:int|None=None, raw_command:str|None=None, raw_method:str|None=None, raw_endpoint:str|None=None, locate_json:str|None=None, deep_think:bool=False, deep_locate:bool=False, approve:bool=False, resume_id:str|None=typer.Option(None,"--resume"), run_id:str|None=None, image:list[str]=typer.Option([],"--image"), image_name:list[str]=typer.Option([],"--image-name"), convert_http_image2_base64:bool=typer.Option(False,"--convert-http-image2-base64"), check_dependencies:bool=typer.Option(False,"--check-dependencies"), json_output:bool=typer.Option(False,"--json")):
    if check_dependencies:
        from ..infrastructure.config.checks import check_dependencies
        typer.echo(json.dumps(check_dependencies(platform))); raise typer.Exit()
    if len(image)!=len(image_name): raise typer.BadParameter("--image and --image-name must be paired")
    target={k:v for k,v in {"url":url,"device_id":device_id,"project_dir":project_dir,"vitest_platform":vitest_platform,"app_uri":app_uri,"cdp":cdp,"bridge":bridge,"wda_host":wda_host,"wda_port":wda_port,"convert_http_image2_base64":convert_http_image2_base64}.items() if v is not None}
    target["reference_images"]=[ReferenceImage(name=n,source=s) for s,n in zip(image,image_name)]
    locate=__import__('json').loads(locate_json) if locate_json else None
    result=execute(AutomationRequest(platform=platform,target=target,goal=goal,operation=operation,mode=mode,report_dir=report_dir,run_id=run_id or resume_id,raw_command=raw_command,raw_method=raw_method,raw_endpoint=raw_endpoint,locate=locate,deep_think=deep_think,deep_locate=deep_locate),approve=approve,resume=bool(resume_id)); typer.echo(result.model_dump_json() if json_output else f"{result.status}: {result.run_id}")
@app.command("vitest")
def vitest(operation:str, project_dir:str, vitest_platform:str, goal:str, mode:str="plan", report_dir:str="./artifacts", test_name:str|None=None, json_output:bool=typer.Option(False,"--json")):
    result=execute(AutomationRequest(platform="vitest_e2e",target={"project_dir":project_dir,"vitest_platform":vitest_platform},goal=goal,operation=operation,mode=mode,report_dir=report_dir,test_name=test_name)); typer.echo(result.model_dump_json() if json_output else f"{result.status}: {result.run_id}")
@app.command("skills")
def skills(action:str, skills_root:str, lock_file:str):
    catalog=SkillCatalog(skills_root); catalog.write_lock(lock_file) if action=="lock" else catalog.verify_lock(lock_file); typer.echo("ok")
def main(): app()
if __name__ == "__main__": main()
