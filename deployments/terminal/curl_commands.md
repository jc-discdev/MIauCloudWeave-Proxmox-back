# Curl Commands / Examples for FastAPI endpoints

This file lists the common curl commands and options to call the FastAPI endpoints in this project. Replace `BASE_URL` and any paths / IDs to match your environment.

---

## Variables used in examples

- `BASE_URL` — e.g. `http://127.0.0.1:8001` (adjust if your server is on another port/host)
- `GCP_CRED` — path to GCP credentials JSON (default `./credentials.json` in repo)
- `AWS_CRED` — path to AWS credentials JSON (default `./credentials_aws.json` in repo)
- `ZONE` — GCP zone, e.g. `europe-west1-b`
- `REGION` — AWS region, default `us-west-2`
- `INSTANCE_NAME` — name of instance (GCP name will be sanitized to valid format; AWS `Name` tag must be prefixed `t3-`)
- `INSTANCE_ID` — AWS instance id (i-...)
- `STATE` — optional state filter (e.g. `RUNNING`, `TERMINATED` for GCP; `running`, `stopped` for AWS)

---

## 1) Delete (combined) — `/all/delete` (deletes across GCP and AWS)

- JSON body example (file): `deployments/astro/all_delete.json` (this file in repo uses credential-file fallback by default)

Example curl (POST JSON file):

```bash
PAYLOAD="$(pwd)/deployments/astro/all_delete.json"

curl -sS -X POST "http://127.0.0.1:8001/all/delete" \
  -H "Content-Type: application/json" \
  -d "@${PAYLOAD}" | jq
```

If you want to delete a specific GCP name and AWS name inline:

```bash
curl -sS -X POST "http://127.0.0.1:8001/all/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "gcp_credentials": "./credentials.json",
    "gcp_name": "t3-mi-instancia-gcp-1",
    "gcp_zone": "europe-west1-b",
    "aws_region": "us-west-2",
    "aws_name": "t3-mi-instancia-aws-1"
  }' | jq
```

Notes:
- The combined endpoint by default reads `credentials.json` and `credentials_aws.json` from the repo directory if inline credentials are not supplied.
- AWS deletion will delete by `instance_id` if provided; otherwise it will look for `Name` tags starting with `t3-`.

---

## 2) Delete GCP only — `/delete`

Use the GCP-specific delete endpoint. This requires `credentials` (path to credentials JSON) in the request body.

Example (delete by name and zone):

```bash
curl -sS -X POST "http://127.0.0.1:8001/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": "./credentials.json",
    "name": "t3-mi-instancia-gcp-1",
    "zone": "europe-west1-b"
  }' | jq
```

If you omit `zone` the server will try to find the instance across zones and delete the first match.

---

## 3) Delete AWS only — `/aws/delete`

Example deleting by instance id (preferred):

```bash
curl -sS -X POST "http://127.0.0.1:8001/aws/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "region": "us-west-2",
    "instance_id": "i-0123456789abcdef0"
  }' | jq
```

Example deleting by `Name` tag (must begin with `t3-`):

```bash
curl -sS -X POST "http://127.0.0.1:8001/aws/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "region": "us-west-2",
    "name": "t3-mi-instancia-aws-1"
  }' | jq
```

If your server cannot find AWS credentials, it will try `deployments/../credentials_aws.json` (repo root `credentials_aws.json`). You can also pass `aws_access_key`, `aws_secret_key`, and `aws_session_token` in the JSON body.

---

## 4) Other useful endpoints and curl notes

- List GCP instances (GET with query params):

```bash
curl -sS -G "http://127.0.0.1:8001/list" \
  --data-urlencode "credentials=./credentials.json" \
  --data-urlencode "zone=europe-west1-b" \
  --data-urlencode "state=RUNNING" | jq
```

- List AWS instances (GET with query params):

```bash
curl -sS -G "http://127.0.0.1:8001/aws/list" \
  --data-urlencode "region=us-west-2" \
  --data-urlencode "state=running" | jq
```

- Combined list `/all/list` (POST with JSON file):

```bash
curl -sS -X POST "http://127.0.0.1:8001/all/list" \
  -H "Content-Type: application/json" \
  -d '@deployments/astro/all_list.json' | jq
```

- Find and create endpoints also exist; look under `deployments/astro/` for example payloads.

---

## 5) Passing credentials securely

- By default the server will read local `credentials.json` (GCP) and `credentials_aws.json` (AWS) from the repo directory. Prefer using local files rather than embedding secrets in payloads.
- If you must send AWS keys inline for a one-off test, include `aws_access_key` and `aws_secret_key` fields in the `/aws/*` or `/all/*` request body.

---

## 6) Quick examples (one-liners)

- Delete GCP instance by name & zone:

```bash
curl -sS -X POST http://127.0.0.1:8001/delete -H "Content-Type: application/json" -d '{"credentials":"./credentials.json","name":"t3-node-1","zone":"europe-west1-b"}' | jq
```

- Delete AWS by name:

```bash
curl -sS -X POST http://127.0.0.1:8001/aws/delete -H "Content-Type: application/json" -d '{"region":"us-west-2","name":"t3-node-aws-1"}' | jq
```

- Combined delete (both providers):

```bash
curl -sS -X POST http://127.0.0.1:8001/all/delete -H "Content-Type: application/json" -d '{"gcp_credentials":"./credentials.json","gcp_name":"t3-node","gcp_zone":"europe-west1-b","aws_region":"us-west-2","aws_name":"t3-node"}' | jq
```

---

If you want, I can also:

- Replace the broken `deployments/terminal/all_list.sh` with the cleaned `all_list_fixed.sh` I created.
- Add a small README or script to help run these commands with environment variables.
- Add examples for using inline AWS credentials securely via environment variables (not in payloads).

Tell me which of those you'd like next.

---

## 7) Create instances (GCP & AWS)

Below are safe example payloads and curl commands to create instances in GCP and AWS. Review the payloads before running — creation will incur cloud resources and possible charges.

### GCP create (`/create`)

Notes: provide the path to your GCP service account JSON in `credentials`. The server will set `GOOGLE_APPLICATION_CREDENTIALS` accordingly.

Example JSON payload (file `deployments/astro/gcp_create.json` style):

```json
{
  "credentials": "./credentials.json",
  "zone": "europe-west1-b",
  "name": "t3-mi-instancia-gcp-1",
  "machine_type": "e2-medium",
  "password": "P@ssw0rd123!"
}
```

Curl (POST from file):

```bash
curl -sS -X POST "http://127.0.0.1:8001/create" \
  -H "Content-Type: application/json" \
  -d '@deployments/astro/gcp_create.json' | jq
```

Inline one-liner (quick test):

```bash
curl -sS -X POST "http://127.0.0.1:8001/create" -H "Content-Type: application/json" \
  -d '{"credentials":"./credentials.json","zone":"europe-west1-b","name":"t3-mi-instancia-gcp-1","machine_type":"e2-medium","password":"P@ssw0rd123!"}' | jq
```

### AWS create (`/aws/create`)

Notes: default AMI used by the server is `ami-03c1f788292172a4e` and default region `us-west-2`. You can override `image_id` and `region` in the payload. AWS credentials are read from `credentials_aws.json` by default or you can pass `aws_access_key`/`aws_secret_key` in the body.

Example JSON payload (file `deployments/astro/aws_create.json` style):

```json
{
  "region": "us-west-2",
  "name": "t3-mi-instancia-aws-1",
  "image_id": "ami-03c1f788292172a4e",
  "instance_type": "t3.micro",
  "password": "P@ssw0rd123!",
  "min_count": 1,
  "max_count": 1
}
```

Curl (POST from file):

```bash
curl -sS -X POST "http://127.0.0.1:8001/aws/create" \
  -H "Content-Type: application/json" \
  -d '@deployments/astro/aws_create.json' | jq
```

Inline one-liner (quick test):

```bash
curl -sS -X POST "http://127.0.0.1:8001/aws/create" -H "Content-Type: application/json" \
  -d '{"region":"us-west-2","name":"t3-mi-instancia-aws-1","image_id":"ami-03c1f788292172a4e","instance_type":"t3.micro","password":"P@ssw0rd123!","min_count":1,"max_count":1}' | jq
```

Notes and tips:
- If you pass `password` for AWS create, the server will attempt to provide it via user-data/cloud-init (if supported). Confirm in your AWS account that the chosen AMI supports cloud-init and password-based login.
- Use `key_name` instead of `password` for keypair-based SSH access if you prefer.
- After creation, use the list endpoints to see created instances and their public IPs.

### Combined create (`/all/create`)

Notes: the combined endpoint will attempt to create resources in both providers when the corresponding payload sections are present. By default the server will read `credentials.json` and `credentials_aws.json` from the repo root if you don't pass credentials inline.

Example JSON payload (file `deployments/astro/all_create.json` style):

```json
{
  "gcp": {
    "credentials": "./credentials.json",
    "zone": "europe-west1-b",
    "name": "t3-mi-instancia-gcp-1",
    "machine_type": "e2-medium",
    "password": "P@ssw0rd123!"
  },
  "aws": {
    "region": "us-west-2",
    "name": "t3-mi-instancia-aws-1",
    "image_id": "ami-03c1f788292172a4e",
    "instance_type": "t3.micro",
    "password": "P@ssw0rd123!",
    "min_count": 1,
    "max_count": 1
  }
}
```

Curl (POST from file):

```bash
curl -sS -X POST "http://127.0.0.1:8001/all/create" \
  -H "Content-Type: application/json" \
  -d '@deployments/astro/all_create.json' | jq
```

Inline quick test (one-liner):

```bash
curl -sS -X POST "http://127.0.0.1:8001/all/create" -H "Content-Type: application/json" \
  -d '{"gcp":{"credentials":"./credentials.json","zone":"europe-west1-b","name":"t3-mi-instancia-gcp-1","machine_type":"e2-medium","password":"P@ssw0rd123!"},"aws":{"region":"us-west-2","name":"t3-mi-instancia-aws-1","image_id":"ami-03c1f788292172a4e","instance_type":"t3.micro","password":"P@ssw0rd123!","min_count":1,"max_count":1}}' | jq
```

Notes:
- If you only want to create on one provider, include only that provider's object (`gcp` or `aws`) in the JSON body.
- Creating resources may incur charges — verify the payload before running.

---

If you want, I can also create the example JSON files (`deployments/astro/gcp_create.json` and `deployments/astro/aws_create.json`) in the repo and add a small `run_create.sh` wrapper that calls them. Want me to add those files now?