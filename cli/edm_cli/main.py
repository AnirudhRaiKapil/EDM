import functools
import json as json_lib
from pathlib import Path

import click

from edm_cli import config
from edm_cli.client import ApiClient, ApiError


def handle_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except ApiError as exc:
            raise click.ClickException(exc.detail)

    return wrapper


def echo_json(data) -> None:
    click.echo(json_lib.dumps(data, indent=2))


@click.group()
def cli():
    """edm - command-line client for the EDM Platform."""


# --- auth -------------------------------------------------------------------

@cli.group()
def auth():
    """Register, log in, and check the current session."""


@auth.command()
@click.option("--email", required=True)
@click.option("--name", "display_name", required=True)
@click.option("--password", required=True, prompt=True, hide_input=True)
@handle_errors
def register(email, display_name, password):
    client = ApiClient(require_auth=False)
    user = client.post("/auth/register", json={"email": email, "display_name": display_name, "password": password})
    echo_json(user)


@auth.command()
@click.option("--email", required=True)
@click.option("--password", required=True, prompt=True, hide_input=True)
@handle_errors
def login(email, password):
    client = ApiClient(require_auth=False)
    token_response = client.post("/auth/login", json={"email": email, "password": password})
    config.save_token(token_response["access_token"], email)
    click.echo(f"Logged in as {email}")


@auth.command()
@handle_errors
def whoami():
    client = ApiClient()
    echo_json(client.get("/users/me"))


@auth.command()
def logout():
    config.clear_token()
    click.echo("Logged out")


# --- workspace ----------------------------------------------------------

@cli.group()
def workspace():
    """Create and manage workspaces and their members."""


@workspace.command("create")
@click.option("--name", required=True)
@click.option("--description", default="")
@handle_errors
def workspace_create(name, description):
    echo_json(ApiClient().post("/workspaces", json={"name": name, "description": description}))


@workspace.command("list")
@handle_errors
def workspace_list():
    echo_json(ApiClient().get("/workspaces"))


@workspace.command("add-member")
@click.option("--workspace-id", required=True)
@click.option("--email", required=True)
@click.option("--role", default="member", type=click.Choice(["owner", "member"]))
@handle_errors
def workspace_add_member(workspace_id, email, role):
    echo_json(
        ApiClient().post(f"/workspaces/{workspace_id}/members", json={"email": email, "role": role})
    )


@workspace.command("members")
@click.option("--workspace-id", required=True)
@handle_errors
def workspace_members(workspace_id):
    echo_json(ApiClient().get(f"/workspaces/{workspace_id}/members"))


# --- project ------------------------------------------------------------

@cli.group()
def project():
    """Create and list projects within a workspace."""


@project.command("create")
@click.option("--workspace-id", required=True)
@click.option("--name", required=True)
@click.option("--environment", default="dev")
@handle_errors
def project_create(workspace_id, name, environment):
    echo_json(
        ApiClient().post(
            f"/workspaces/{workspace_id}/projects", json={"name": name, "environment": environment}
        )
    )


@project.command("list")
@click.option("--workspace-id", required=True)
@handle_errors
def project_list(workspace_id):
    echo_json(ApiClient().get(f"/workspaces/{workspace_id}/projects"))


# --- source ---------------------------------------------------------------

@cli.group()
def source():
    """Register data sources and upload files to them."""


@source.command("create")
@click.option("--project-id", required=True)
@click.option("--name", required=True)
@click.option("--connector-type", default="csv", type=click.Choice(["csv", "json", "sqlite"]))
@click.option("--connection-config", default=None, help="JSON string, e.g. for sqlite: "
              '\'{"db_path": "C:/data/app.db", "table": "customers"}\'')
@handle_errors
def source_create(project_id, name, connector_type, connection_config):
    payload = {"name": name, "connector_type": connector_type}
    if connection_config:
        payload["connection_config"] = json_lib.loads(connection_config)
    echo_json(ApiClient().post(f"/projects/{project_id}/sources", json=payload))


@source.command("list")
@click.option("--project-id", required=True)
@handle_errors
def source_list(project_id):
    echo_json(ApiClient().get(f"/projects/{project_id}/sources"))


@source.command("upload")
@click.option("--source-id", required=True)
@click.option("--file", "file_path", required=True, type=click.Path(exists=True))
@handle_errors
def source_upload(source_id, file_path):
    with open(file_path, "rb") as fh:
        result = ApiClient().post(
            f"/sources/{source_id}/upload", files={"file": (Path(file_path).name, fh)}
        )
    echo_json(result)


# --- pipeline ---------------------------------------------------------------

@cli.group()
def pipeline():
    """Define and run pipelines."""


@pipeline.command("create")
@click.option("--project-id", required=True)
@click.option("--name", required=True)
@click.option("--source-id", required=True)
@click.option("--output-dataset-name", required=True)
@click.option("--output-layer", default="silver", type=click.Choice(["bronze", "silver", "gold"]))
@click.option(
    "--transformations",
    default="[]",
    help='JSON array, e.g. \'[{"type": "standardize"}, {"type": "dedupe"}]\'',
)
@handle_errors
def pipeline_create(project_id, name, source_id, output_dataset_name, output_layer, transformations):
    payload = {
        "name": name,
        "source_id": source_id,
        "output_dataset_name": output_dataset_name,
        "output_layer": output_layer,
        "transformations": json_lib.loads(transformations),
    }
    echo_json(ApiClient().post(f"/projects/{project_id}/pipelines", json=payload))


@pipeline.command("list")
@click.option("--project-id", required=True)
@handle_errors
def pipeline_list(project_id):
    echo_json(ApiClient().get(f"/projects/{project_id}/pipelines"))


@pipeline.command("get")
@click.option("--pipeline-id", required=True)
@handle_errors
def pipeline_get(pipeline_id):
    echo_json(ApiClient().get(f"/pipelines/{pipeline_id}"))


@pipeline.command("run")
@click.option("--pipeline-id", required=True)
@handle_errors
def pipeline_run(pipeline_id):
    echo_json(ApiClient().post(f"/pipelines/{pipeline_id}/jobs"))


# --- job ----------------------------------------------------------------

@cli.group()
def job():
    """Inspect job runs."""


@job.command("list")
@click.option("--pipeline-id", required=True)
@handle_errors
def job_list(pipeline_id):
    echo_json(ApiClient().get(f"/pipelines/{pipeline_id}/jobs"))


@job.command("get")
@click.option("--job-id", required=True)
@handle_errors
def job_get(job_id):
    echo_json(ApiClient().get(f"/jobs/{job_id}"))


# --- catalog --------------------------------------------------------------

@cli.group()
def catalog():
    """Search the catalog and manage dataset tags/classification."""


@catalog.command("search")
@click.option("--project-id", default=None)
@click.option("--q", default=None, help="substring search on dataset name")
@click.option("--tag-key", default=None)
@click.option("--tag-value", default=None)
@handle_errors
def catalog_search(project_id, q, tag_key, tag_value):
    params = {k: v for k, v in {
        "project_id": project_id, "q": q, "tag_key": tag_key, "tag_value": tag_value
    }.items() if v is not None}
    echo_json(ApiClient().get("/catalog/datasets", params=params))


@catalog.command("get")
@click.option("--dataset-id", required=True)
@handle_errors
def catalog_get(dataset_id):
    echo_json(ApiClient().get(f"/catalog/datasets/{dataset_id}"))


@catalog.command("classify")
@click.option("--dataset-id", required=True)
@click.option("--classification", required=True, help='JSON array, e.g. \'["pii", "confidential"]\'')
@handle_errors
def catalog_classify(dataset_id, classification):
    payload = {"classification": json_lib.loads(classification)}
    echo_json(ApiClient().patch(f"/catalog/datasets/{dataset_id}", json=payload))


@catalog.command("tag")
@click.option("--dataset-id", required=True)
@click.option("--key", required=True)
@click.option("--value", required=True)
@handle_errors
def catalog_tag(dataset_id, key, value):
    echo_json(ApiClient().post(f"/catalog/datasets/{dataset_id}/tags", json={"key": key, "value": value}))


@catalog.command("untag")
@click.option("--dataset-id", required=True)
@click.option("--tag-id", required=True)
@handle_errors
def catalog_untag(dataset_id, tag_id):
    ApiClient().delete(f"/catalog/datasets/{dataset_id}/tags/{tag_id}")
    click.echo("Tag removed")


# --- quality --------------------------------------------------------------

@cli.group()
def quality():
    """Manage data quality rules and inspect quality run history."""


@quality.command("add-rule")
@click.option("--dataset-id", required=True)
@click.option("--expectation-type", required=True,
              type=click.Choice(["not_null", "unique", "min", "max", "regex", "allowed_values"]))
@click.option("--column", required=True)
@click.option("--severity", default="blocking", type=click.Choice(["warning", "blocking"]))
@click.option("--value", default=None, help="for min/max")
@click.option("--pattern", default=None, help="for regex")
@click.option("--values", default=None, help="JSON array, for allowed_values")
@handle_errors
def quality_add_rule(dataset_id, expectation_type, column, severity, value, pattern, values):
    parameters = {"column": column}
    if value is not None:
        parameters["value"] = float(value) if "." in value else int(value)
    if pattern is not None:
        parameters["pattern"] = pattern
    if values is not None:
        parameters["values"] = json_lib.loads(values)
    payload = {"expectation_type": expectation_type, "parameters": parameters, "severity": severity}
    echo_json(ApiClient().post(f"/catalog/datasets/{dataset_id}/quality-rules", json=payload))


@quality.command("list-rules")
@click.option("--dataset-id", required=True)
@handle_errors
def quality_list_rules(dataset_id):
    echo_json(ApiClient().get(f"/catalog/datasets/{dataset_id}/quality-rules"))


@quality.command("list-runs")
@click.option("--dataset-id", required=True)
@handle_errors
def quality_list_runs(dataset_id):
    echo_json(ApiClient().get(f"/catalog/datasets/{dataset_id}/quality-runs"))


# --- query ----------------------------------------------------------------

@cli.command("query")
@click.option("--dataset-id", required=True)
@click.option("--sql", required=True)
@handle_errors
def run_query(dataset_id, sql):
    echo_json(ApiClient().post("/query", json={"dataset_id": dataset_id, "sql": sql}))


if __name__ == "__main__":
    cli()
