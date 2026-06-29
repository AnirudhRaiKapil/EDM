# edm-cli

A thin command-line client over the `edm-platform` REST API — the same interface a real user
drives the platform with, instead of raw `curl`. See
[03-engineering-principles.md](../docs/03-engineering-principles.md) Rule 9 (Developer
Experience Matters) and the original design conversation's `edm source create` /
`edm pipeline run` examples this mirrors.

## Install

```
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

This registers an `edm` console command inside `.venv\Scripts\`.

## Configuration

- `EDM_API_URL` — defaults to `http://localhost:8000/api/v1`
- Credentials (bearer token) are saved to `~/.edm/credentials.json` after `edm auth login`, so
  you don't need to re-authenticate for every command.

## The golden path

```
edm auth register --email you@example.com --name "Your Name" --password ...
edm auth login --email you@example.com --password ...

edm workspace create --name acme
edm project create --workspace-id <id> --name sales --environment dev

edm source create --project-id <id> --name customers-csv --connector-type csv
edm source upload --source-id <id> --file ./customers.csv

# any of oracle/s3/rest_api/servicenow/jira/confluence/postgres/mysql/mongodb/google_sheets, e.g.:
edm source create --project-id <id> --name snow-incidents --connector-type servicenow \
  --connection-config '{"instance_url": "https://x.service-now.com", "table": "incident"}' \
  --credentials '{"username": "admin", "password": "..."}'

edm pipeline create --project-id <id> --name standardize-customers --source-id <id> \
  --output-dataset-name customers --output-layer silver \
  --transformations '[{"type": "standardize"}, {"type": "dedupe"}]'
edm pipeline run --pipeline-id <id>
edm pipeline schedule --pipeline-id <id> --cron "0 * * * *"   # hourly; --clear to remove

# Notebook: write code in cells, run against a sample, then promote into the pipeline above's
# kind of object — a real, schedulable Pipeline (see ADR-0010)
edm notebook create --project-id <id> --name explore --source-id <id> --sample-size 100
edm notebook add-cell --notebook-id <id> --code "df = df.drop_duplicates()"
edm notebook run --notebook-id <id>
edm notebook promote --notebook-id <id> --output-dataset-name customers_clean

edm catalog search --project-id <id>
edm catalog get --dataset-id <id>

edm quality add-rule --dataset-id <id> --expectation-type not_null --column email --severity blocking
edm quality list-runs --dataset-id <id>

edm lineage dataset --dataset-id <id>

edm alert list --project-id <id>
edm alert acknowledge --alert-id <id>
edm alert resolve --alert-id <id>

# Notification channels: every Alert on the project fans out to these (ADR-0011, +slack/teams ADR-0012)
edm notification create --project-id <id> --type webhook --url https://hooks.example.com/edm
edm notification create --project-id <id> --type slack --url https://hooks.slack.com/services/...
edm notification create --project-id <id> --type email --to-address oncall@example.com
edm notification list --project-id <id>

# Audit log: immutable record of logins, role/credential/schedule changes (ADR-0011)
edm audit workspace --workspace-id <id>   # owner-only
edm audit me                              # your own login/registration history

edm query --dataset-id <id> --sql "SELECT * FROM dataset LIMIT 10"
```

Run `edm --help` or `edm <group> --help` for the full command list (`auth`, `workspace`,
`project`, `source`, `pipeline`, `notebook`, `job`, `catalog`, `quality`, `lineage`, `alert`,
`audit`, `notification`, `query`). All output is JSON; errors print a one-line message and exit
non-zero, so the CLI is scriptable.

## Why a CLI before a UI

Every part of `edm-platform` had only ever been exercised through `pytest`'s `TestClient` or raw
`curl` — nothing resembling how an actual user would touch it. This CLI is a real consumer of the
HTTP API (multipart uploads, auth headers, error bodies) and caught a real bug during that first
end-to-end run: the upload command was sending an absolute file path as the multipart filename,
which the server then used verbatim as part of a storage path — fixed in
`edm_cli/main.py` (basename only) and hardened server-side in
`app/modules/storage/adapter.py` (`Path(filename).name` strips any path components the client
sends, closing the path-traversal angle regardless of client behavior).
