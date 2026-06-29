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
@click.option(
    "--connector-type",
    default="csv",
    type=click.Choice(
        [
            "csv",
            "json",
            "sqlite",
            "oracle",
            "s3",
            "rest_api",
            "servicenow",
            "jira",
            "confluence",
            "postgres",
            "mysql",
            "mongodb",
            "google_sheets",
        ]
    ),
)
@click.option(
    "--connection-config",
    default=None,
    help='JSON string, e.g. for sqlite: \'{"db_path": "C:/data/app.db", "table": "customers"}\'; '
    'for oracle: \'{"host": "...", "port": 1521, "service_name": "...", "table": "..."}\'; '
    'for postgres/mysql: \'{"host": "...", "port": 5432, "database": "...", "table": "..."}\'; '
    'for mongodb: \'{"host": "...", "port": 27017, "database": "...", "collection": "..."}\'; '
    'for s3: \'{"bucket": "...", "key": "data/file.csv"}\'; '
    'for servicenow: \'{"instance_url": "https://x.service-now.com", "table": "incident"}\'; '
    'for jira/confluence: \'{"base_url": "https://x.atlassian.net", "jql": "..."}\'; '
    'for google_sheets: \'{"spreadsheet_id": "...", "range": "Sheet1!A1:B10"}\'',
)
@click.option(
    "--credentials",
    default=None,
    help='JSON string, e.g. \'{"username": "...", "password": "..."}\', '
    '\'{"email": "...", "api_token": "..."}\', or \'{"api_key": "..."}\' (google_sheets) -- '
    "optional for mongodb/s3, encrypted at rest, never returned by the API.",
)
@handle_errors
def source_create(project_id, name, connector_type, connection_config, credentials):
    payload = {"name": name, "connector_type": connector_type}
    if connection_config:
        payload["connection_config"] = json_lib.loads(connection_config)
    if credentials:
        payload["credentials"] = json_lib.loads(credentials)
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


@pipeline.command("schedule")
@click.option("--pipeline-id", required=True)
@click.option("--cron", default=None, help='Standard 5-field cron, e.g. "0 * * * *" for hourly.')
@click.option("--clear", is_flag=True, help="Remove the schedule instead of setting one.")
@handle_errors
def pipeline_schedule(pipeline_id, cron, clear):
    if clear:
        cron = None
    elif not cron:
        raise click.UsageError("pass --cron '<expression>' or --clear")
    echo_json(ApiClient().patch(f"/pipelines/{pipeline_id}/schedule", json={"cron": cron}))


# --- notebook -----------------------------------------------------------

@cli.group()
def notebook():
    """Write and run code interactively against a sample of a source's data,
    then promote it into a scheduled pipeline once it works."""


@notebook.command("create")
@click.option("--project-id", required=True)
@click.option("--name", required=True)
@click.option("--source-id", required=True)
@click.option("--sample-size", default=100, type=int, help="Rows to sample for fast iteration.")
@handle_errors
def notebook_create(project_id, name, source_id, sample_size):
    echo_json(
        ApiClient().post(
            f"/projects/{project_id}/notebooks",
            json={"name": name, "source_id": source_id, "sample_size": sample_size},
        )
    )


@notebook.command("list")
@click.option("--project-id", required=True)
@handle_errors
def notebook_list(project_id):
    echo_json(ApiClient().get(f"/projects/{project_id}/notebooks"))


@notebook.command("get")
@click.option("--notebook-id", required=True)
@handle_errors
def notebook_get(notebook_id):
    echo_json(ApiClient().get(f"/notebooks/{notebook_id}"))


@notebook.command("add-cell")
@click.option("--notebook-id", required=True)
@click.option("--code", required=True, help="Python source for the cell (pandas available as pd, df is the dataframe).")
@click.option("--order", default=None, type=int)
@handle_errors
def notebook_add_cell(notebook_id, code, order):
    payload = {"code": code}
    if order is not None:
        payload["order"] = order
    echo_json(ApiClient().post(f"/notebooks/{notebook_id}/cells", json=payload))


@notebook.command("update-cell")
@click.option("--notebook-id", required=True)
@click.option("--cell-id", required=True)
@click.option("--code", required=True)
@handle_errors
def notebook_update_cell(notebook_id, cell_id, code):
    echo_json(ApiClient().patch(f"/notebooks/{notebook_id}/cells/{cell_id}", json={"code": code}))


@notebook.command("delete-cell")
@click.option("--notebook-id", required=True)
@click.option("--cell-id", required=True)
@handle_errors
def notebook_delete_cell(notebook_id, cell_id):
    ApiClient().delete(f"/notebooks/{notebook_id}/cells/{cell_id}")
    click.echo("Cell deleted")


@notebook.command("run")
@click.option("--notebook-id", required=True)
@click.option("--up-to-cell-id", default=None, help="Stop after this cell instead of running all of them.")
@handle_errors
def notebook_run(notebook_id, up_to_cell_id):
    params = {"up_to_cell_id": up_to_cell_id} if up_to_cell_id else None
    echo_json(ApiClient().post(f"/notebooks/{notebook_id}/run", params=params))


@notebook.command("promote")
@click.option("--notebook-id", required=True)
@click.option("--output-dataset-name", required=True)
@click.option("--output-layer", default="silver")
@click.option("--pipeline-name", default=None)
@handle_errors
def notebook_promote(notebook_id, output_dataset_name, output_layer, pipeline_name):
    payload = {"output_dataset_name": output_dataset_name, "output_layer": output_layer}
    if pipeline_name:
        payload["pipeline_name"] = pipeline_name
    echo_json(ApiClient().post(f"/notebooks/{notebook_id}/promote", json=payload))


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


# --- lineage ----------------------------------------------------------------

@cli.group()
def lineage():
    """Trace what fed into (upstream) or consumes from (downstream) an entity."""


@lineage.command("dataset")
@click.option("--dataset-id", required=True)
@handle_errors
def lineage_dataset(dataset_id):
    echo_json(ApiClient().get(f"/lineage/datasets/{dataset_id}"))


@lineage.command("source")
@click.option("--source-id", required=True)
@handle_errors
def lineage_source(source_id):
    echo_json(ApiClient().get(f"/lineage/sources/{source_id}"))


@lineage.command("pipeline")
@click.option("--pipeline-id", required=True)
@handle_errors
def lineage_pipeline(pipeline_id):
    echo_json(ApiClient().get(f"/lineage/pipelines/{pipeline_id}"))


# --- alerts -----------------------------------------------------------------

@cli.group()
def alert():
    """List and triage alerts raised by failed jobs or quality warnings."""


@alert.command("list")
@click.option("--project-id", required=True)
@click.option("--status", default=None, type=click.Choice(["open", "acknowledged", "resolved"]))
@handle_errors
def alert_list(project_id, status):
    params = {"status": status} if status else None
    echo_json(ApiClient().get(f"/projects/{project_id}/alerts", params=params))


@alert.command("acknowledge")
@click.option("--alert-id", required=True)
@handle_errors
def alert_acknowledge(alert_id):
    echo_json(ApiClient().patch(f"/alerts/{alert_id}", json={"status": "acknowledged"}))


@alert.command("resolve")
@click.option("--alert-id", required=True)
@handle_errors
def alert_resolve(alert_id):
    echo_json(ApiClient().patch(f"/alerts/{alert_id}", json={"status": "resolved"}))


# --- audit ------------------------------------------------------------------

@cli.group()
def audit():
    """Immutable log of security-sensitive actions (logins, credential changes,
    role/schedule changes)."""


@audit.command("workspace")
@click.option("--workspace-id", required=True)
@click.option("--limit", default=100, type=int)
@handle_errors
def audit_workspace(workspace_id, limit):
    echo_json(ApiClient().get(f"/workspaces/{workspace_id}/audit-events", params={"limit": limit}))


@audit.command("me")
@click.option("--limit", default=100, type=int)
@handle_errors
def audit_me(limit):
    echo_json(ApiClient().get("/users/me/audit-events", params={"limit": limit}))


# --- notification -------------------------------------------------------------

@cli.group()
def notification():
    """Webhook/email/Slack/Teams channels that fire when an Alert is created."""


@notification.command("create")
@click.option("--project-id", required=True)
@click.option(
    "--type", "channel_type", required=True, type=click.Choice(["webhook", "email", "slack", "teams"])
)
@click.option("--url", default=None, help="Required for --type webhook/slack/teams.")
@click.option("--to-address", default=None, help="Required for --type email.")
@handle_errors
def notification_create(project_id, channel_type, url, to_address):
    config = {"url": url} if channel_type in ("webhook", "slack", "teams") else {"to_address": to_address}
    echo_json(
        ApiClient().post(
            f"/projects/{project_id}/notification-channels",
            json={"type": channel_type, "config": config},
        )
    )


@notification.command("list")
@click.option("--project-id", required=True)
@handle_errors
def notification_list(project_id):
    echo_json(ApiClient().get(f"/projects/{project_id}/notification-channels"))


@notification.command("delete")
@click.option("--channel-id", required=True)
@handle_errors
def notification_delete(channel_id):
    ApiClient().delete(f"/notification-channels/{channel_id}")
    click.echo("Channel deleted")


# --- query ----------------------------------------------------------------

@cli.command("query")
@click.option("--dataset-id", required=True)
@click.option("--sql", required=True)
@handle_errors
def run_query(dataset_id, sql):
    echo_json(ApiClient().post("/query", json={"dataset_id": dataset_id, "sql": sql}))


if __name__ == "__main__":
    cli()
