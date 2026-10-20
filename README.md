# MLonMCU DB

Store and inspect MLonMCU experiments and their artifacts. PostgreSQL holds
experiment metadata and artifact references; Garage provides S3-compatible object
storage for reports and other files. A Python CLI lists experiments, displays CSV
reports, and downloads artifacts.

## Requirements

- Docker with Docker Compose
- Python 3 with `venv` and `pip`

## Setup

Run the commands below from the repository root.

### 1. Configure the services

```bash
cp .env.sample .env
```

Edit `.env` and replace all `<enter ...>` placeholders. Quote values containing
spaces or shell metacharacters so the file can also be sourced by Bash. The S3
credentials will be filled in after creating a Garage key below.

Generate a Garage RPC secret with `openssl rand -hex 32` and set
`GARAGE_RPC_SECRET` in `.env`. In `garage/garage.toml`, replace the literal
`${GARAGE_RPC_SECRET}` in `rpc_secret` with that same value: the file is mounted
directly, and Compose does not substitute variables inside it. Replace
`YOUR_ADMIN_TOKEN_HERE` and `YOUR_METRICS_TOKEN_HERE` with generated secrets too.
Keep credentials and configured secrets out of commits.

### 2. Start PostgreSQL and Garage

```bash
docker compose up -d postgres garage
docker compose logs postgres garage
```

Wait until both services are ready before continuing. PostgreSQL runs the schema
in `db-init/` when its data volume is first initialized.

For a fresh, single-node Garage instance, assign storage capacity and apply its
initial layout:

```bash
docker compose exec garage /garage node id
```

Use the returned node ID in place of `NODE_ID` below. The example allocates 1 GiB;
choose a larger capacity if you plan to upload large artifacts.

```bash
docker compose exec garage /garage layout assign NODE_ID -z dc1 -c 1G
docker compose exec garage /garage layout show
docker compose exec garage /garage layout apply --version 1
docker compose exec garage /garage bucket create mlonmcu
docker compose exec garage /garage key create mlonmcu-key
docker compose exec garage /garage bucket allow mlonmcu --read --write --owner --key mlonmcu-key
docker compose exec garage /garage status
```

Save the generated key ID as `S3_KEY` and its secret as `S3_SECRET` in `.env`.
These layout and key creation commands are for initial setup, not routine restarts.

`init.sh` contains a similar initialization sequence, but assumes the bucket
already exists, applies layout version 1, and creates a new key each time. Use
the explicit steps above for a fresh installation.

### 3. Install the Python client

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
source .env
```

The sample environment file uses `export`, which makes the variables available
to the Python scripts. Source it again after changing credentials or opening a
new shell. The scripts do not load `.env` themselves.

## Configuration

| Variable | Purpose | Python default |
| --- | --- | --- |
| `POSTGRES_USER` | Database user | `mlonmcu` |
| `POSTGRES_PASSWORD` | Database password | Required |
| `POSTGRES_DB` | Database name | `mlonmcu` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `S3_ENDPOINT` | S3 API endpoint | `http://localhost:3900` |
| `S3_KEY` | Garage key ID | Required |
| `S3_SECRET` | Garage key secret | Required |

The scripts use S3 region `garage`; both upload examples use bucket `mlonmcu`.
All three required credentials must be set even when running `client.py --help`.

Compose also reads the Garage and web UI variables in `.env`. The web UI uses
`S3_ENDPOINT_URL` for its container-side endpoint; the Python scripts use
`S3_ENDPOINT`.

## Usage

### Upload a sample experiment

```bash
python upload.py
```

This creates a `test-run` experiment with `board=qemu` and `opt=O2` tags,
uploads a small example CSV report to
`mlonmcu/experiments/<id>/report.csv`, and registers its artifact metadata in
PostgreSQL. Each invocation creates a new experiment. This is a demonstration
script; it has no command-line arguments for uploading your own report.

### Browse experiments and retrieve artifacts

Replace `1` with an experiment ID returned by an upload or the list command.

```bash
python client.py list
python client.py list --label test-run
python client.py list --after 2026-01-01 --before 2026-12-31
python client.py list --tags board opt
python client.py show 1
python client.py artifacts 1
python client.py report 1
python client.py download 1 --out downloads
python client.py download 1 --type report --out downloads/reports
```

`list` returns up to 50 experiments, newest first. Filters can be combined;
`--tags` matches experiments containing any of the supplied JSON tag **keys**.
Date bounds are inclusive. `report` reads the first registered CSV report and
prints its first 50 rows. Downloads default to `downloads/` and use each object's
basename, so files with the same basename can overwrite one another.

### Large-file upload example

`upload_dummy.py` uploads the sample report plus an existing file at
`/tmp/dummy2gb.bin`, registering the latter as type `dummy2gb`. Create that file
first and ensure Garage has enough configured capacity and free disk space.

```bash
python upload_dummy.py
```

### Optional Garage web UI

Set `AUTH_USER_PASS` in `.env` and configure the Garage admin token in
`garage/garage.toml` before starting the UI:

```bash
docker compose up -d webui
```

Open <http://localhost:3909>. The repository also includes `hash_pw.py` for
generating bcrypt password hashes; it requires an additional dependency:

```bash
python -m pip install bcrypt
python hash_pw.py 'your-password'
```

### Optional experiment explorer

The experiment explorer exposes the Python client's browsing and download
features through a responsive web app. It is separate from the Garage admin UI
and starts only when explicitly requested:

```bash
docker compose --profile explorer up -d --build explorer
```

Open <http://localhost:8080>. If that port is occupied, choose another port:

```bash
EXPLORER_PORT=8088 docker compose --profile explorer up -d --build explorer
```

The interface includes:

- A paginated experiment sidebar with labels, timestamps, tags, distinct run
  counts, and artifact counts. Runs are distinct numeric `runs/<id>/` directories
  found in artifact types or S3 keys; experiments without such paths show zero.
- Exact-label, inclusive timestamp, and match-any tag filters, matching the CLI's
  semantics. Enter comma-separated tag keys (or tag names for JSON tag arrays).
- Experiment details, notes, configuration hashes, and raw metadata.
- Artifact type filtering, individual downloads, and ZIP downloads of all
  artifacts or a selected type. ZIP entries include artifact IDs to avoid filename
  collisions.
- CSV report selection, searchable and sortable tables, and numeric metric charts.
  Preview is limited to 1,000 rows and 5 MiB per report; full downloads remain
  available. Charts show the first 20 visible rows.

Database and S3 credentials come from `.env` and remain on the server. Compose
sets the container-side database and S3 hosts automatically. The service runs
database queries in read-only transactions and binds to loopback by default; it
has no login screen. Use an authenticated TLS proxy for shared access.

Individual downloads stream from S3. ZIP downloads are assembled in the
container's temporary directory before delivery, so allow enough temporary disk
space and download time for large bundles. The Gunicorn worker timeout is 300
seconds. `/healthz` checks the web process; storage failures are reported by the
data endpoints and displayed in the interface.

To stop just the explorer:

```bash
docker compose --profile explorer stop explorer
```

For local development and backend tests:

```bash
python -m pip install -r webapp/requirements.txt pytest
source .env
flask --app webapp.app:create_app run --port 8080
python -m pytest tests -q
```

Optional browser tests require `pip install playwright`,
`python -m playwright install chromium`, and
`RUN_BROWSER_TESTS=1 python -m pytest tests -q`. Set `TEST_DATABASE_URL` to a
PostgreSQL connection URL to also check filtering and distinct run counts against
PostgreSQL; those tests use temporary tables on their own connection.

## Data and service management

| Service | Host port | Persistent storage |
| --- | --- | --- |
| PostgreSQL 16 | `5432` | Compose volume `postgres-data` |
| Garage S3 API | `3900` | `data/` and `meta/` |
| Garage RPC | `3901` | Same Garage directories |
| Garage static website endpoint | `3902` | Same Garage directories |
| Garage admin API | `3903` | Same Garage directories |
| Garage web UI | `3909` | Uses Garage |
| Experiment explorer (optional) | `8080` (loopback; configurable) | Uses PostgreSQL and Garage |

The schema contains two tables:

- `experiments`: ID, label, timestamp, configuration hash, notes, and JSON tags.
- `artifacts`: ID, experiment reference, type, size in bytes, and JSON metadata
  containing the S3 `bucket` and `s3_key`.

```bash
docker compose ps
docker compose logs -f postgres garage
docker compose down
```

`docker compose down` stops the services while retaining their data. Adding
`--volumes` deletes the PostgreSQL volume; Garage data remains in the bind-mounted
directories. Back up PostgreSQL and Garage together to preserve artifact references
and their objects. Schema changes in `db-init/` are not applied automatically to
an existing PostgreSQL volume.

The supplied Compose file publishes service ports on the host, and Garage is
configured with a single replica. Restrict access and configure appropriate
authentication and TLS before exposing the services beyond a trusted environment.

## Troubleshooting

- An assertion on startup usually means `POSTGRES_PASSWORD`, `S3_KEY`, or
  `S3_SECRET` is missing from the shell environment. Check `.env` and source it.
- For database connection errors, check PostgreSQL logs and the `POSTGRES_*`
  settings. Changing `.env` does not change credentials in an existing database.
- For S3 errors, verify the endpoint, bucket, key permissions, and applied Garage
  layout with `/garage status`, `/garage bucket list`, and `/garage key list`
  through `docker compose exec garage`.
- The artifact listing currently looks for metadata field `object`, while the
  upload scripts store `s3_key`, so its Object column can display `?`. Downloads
  and report viewing use `s3_key`.
