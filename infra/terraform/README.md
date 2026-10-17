# MealShopper GCP deployment

This configuration provisions the VPC and private services access, PostgreSQL,
Redis, Firestore, storage, private Cloud Run backend services, a public HTTPS
load balancer, and a static frontend bucket. Cloud Run backend services
are IAM-invoker protected. Only the gateway can be invoked publicly, and it is
reachable through the load balancer.

## Prerequisites

- A GCP project with billing enabled and permissions to enable APIs, create the
  listed resources, and grant the configured IAM roles.
- Terraform 1.5+ and Google provider `~> 6.0`.
- Application Default Credentials for local use, or Workload Identity
  Federation/service-account impersonation for automation. Do not create a
  service-account JSON key for Terraform.
- A DNS name you control for the frontend.

## Required variables

Provide these through a protected `.tfvars` file kept out of source control or
through `TF_VAR_...` environment variables:

| Variable | Purpose |
| --- | --- |
| `project_id` | GCP project ID |
| `sql_password` | PostgreSQL administrator password |
| `users_db_password` | Dedicated password for the Users service database role |
| `shopper_db_password` | Dedicated password for the Shopper service database role |
| `worker_bucket_name` | Globally unique private worker-file bucket name |
| `web_bucket_name` | Globally unique public static-site bucket name |
| `frontend_domain` | DNS hostname for the HTTPS load balancer |
| `orchestrator_image` | Published Artifact Registry image for the C# orchestrator |
| `identity_image` | Published Artifact Registry image for the Identity service |
| `user_service_image` | Published Artifact Registry image for the Users service |
| `planning_domain_image` | Published Artifact Registry image for the Python planning API |
| `shopper_domain_image` | Published Artifact Registry image for the Python shopper API |
| `gateway_image` | Published Artifact Registry image for the API gateway |
| `cloud_run_deletion_protection` | Optional; defaults to `true` to protect services from accidental deletion |

The SQL password is marked sensitive, but the Cloud SQL provider stores its
configured values in Terraform state. Configure encrypted, access-controlled
remote state before applying; do not commit state or plaintext variable files.
Use separate random values for the administrator, Users, and Shopper passwords.
Do not reuse local development credentials in production. Terraform manages the
two application-role passwords, while Cloud Run reads the matching password
from each service's dedicated Secret Manager secret. Add the Users and Shopper
passwords to the protected `deployment.tfvars` file as `users_db_password` and
`shopper_db_password`; never pass secret values on the Terraform command line.
For example, `openssl rand -hex 32` generates a high-entropy value suitable
for each password; use a different value each time.

Cloud SQL uses the Enterprise edition and defaults to `db-f1-micro`, its
lowest-cost shared-core tier. Cloud SQL does not provide a generally available
always-free tier; storage, backups, and other usage can still incur charges.
`db-f1-micro` has limited CPU and memory and is intended for development or
testing, not production workloads.

## Initialize and provision

```powershell
gcloud auth application-default login
terraform init
terraform fmt -check
terraform validate
```

The Artifact Registry repository and Secret Manager containers must exist before
images can be pushed and secret versions can be created. Bootstrap only those
resources first, using the same protected variable file that will be used for
the complete deployment:

```powershell
terraform apply `
  -var-file="deployment.tfvars" `
  -target="google_artifact_registry_repository.mealshopper" `
  -target="google_secret_manager_secret.db_password" `
  -target="google_secret_manager_secret.users_db_password" `
  -target="google_secret_manager_secret.shopper_db_password" `
  -target="google_secret_manager_secret.orchestrator_client_secret" `
  -target="google_secret_manager_secret.jwt_signing_key" `
  -target="google_secret_manager_secret.gemini_api_key"
  ```

After the bootstrap apply, add versions to the Users and Shopper DB secrets
using the exact same values provided in `deployment.tfvars`. For example, with
each value in a protected file, use
`gcloud secrets versions add mealshopper-shopper-db-password --data-file=<protected-file>`.
Do not put secret values in command arguments or terminal history. Then build
and push all six images to the Artifact Registry repository, and set the image
variables to their full image URIs. The full apply updates the PostgreSQL
application-role passwords first, then rolls out Cloud Run revisions that read
the new dedicated secrets.

```powershell
terraform plan -var-file="deployment.tfvars" -out="mealshopper.tfplan"
terraform apply "mealshopper.tfplan"
```

## Destroying the deployment

Cloud Run deletion protection defaults to enabled. To destroy the deployment,
first disable protection and apply that change, then run destroy with protection
still disabled:

```powershell
terraform apply -var-file=deployment.tfvars `
  -var="cloud_run_deletion_protection=false" `
  -target=google_cloud_run_v2_service.planning_domain `
  -target=google_cloud_run_v2_service.shopper_domain `
  -target=google_cloud_run_v2_service.user_service

terraform destroy -var-file=deployment.tfvars `
  -var="cloud_run_deletion_protection=false" `
  -var="sql_deletion_protection=false"
```

Target only Cloud Run services that already exist in state when running the
preparatory apply; targeting a service that has not been created can create it.
If `google_sql_database_instance.mealshopper` appears in
`terraform state list`, add
`-target=google_sql_database_instance.mealshopper -var="sql_deletion_protection=false"`
to the preparatory apply as well.
`terraform destroy` removes all resources managed by this state, not just
Cloud Run services. Review its plan carefully before confirming. If Cloud SQL
was created, its deletion protection must be disabled and applied before it
can be destroyed.

## Populate Secret Manager

Terraform creates the secret containers, but intentionally does not create
secret versions. Add versions outside Terraform before expecting services to
start:

- `mealshopper-db-password`: optional administrator-password copy; Cloud Run
  does not use this secret.
- `mealshopper-users-db-password`: use the same value supplied as
  `users_db_password`.
- `mealshopper-shopper-db-password`: use the same value supplied as
  `shopper_db_password`.
- `mealshopper-orchestrator-client-secret`: use the same secret configured for
  the `orchestrator-client` in the Identity service.
- `mealshopper-jwt-signing-key`: a PEM-encoded RSA private key. Keep it stable
  so tokens remain verifiable across instances and restarts.
- `mealshopper-gemini-api-key`: the Gemini API key used by the planning and
  shopper services.

For example, pipe a protected file to `gcloud secrets versions add` rather than
putting the value on a command line or in Terraform. Do not enable shell
tracing while handling secret values.

## Database initialization

The Users and Shopper containers run their SQL scripts at startup as
`users_app` and `shopper_app`. After Terraform creates the databases, grant
those roles permission to create objects in their respective databases before
restarting the Cloud Run services:

```sql
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE mealshopper_users TO users_app;
GRANT USAGE, CREATE ON SCHEMA public TO users_app;

GRANT CONNECT, CREATE, TEMPORARY ON DATABASE mealshopper_shopper TO shopper_app;
GRANT USAGE, CREATE ON SCHEMA public TO shopper_app;
```

Run the statements as a Cloud SQL administrator, connecting to each database
for its schema grant. Review the repository SQL scripts before production use.

To verify the Shopper startup migrations, inspect the Cloud Run service logs:

```powershell
gcloud run services logs read mealshopper-shopper --region=us-west1 --project=<project_id> --limit=100
```

Look for `Migrations successfully completed`. A log showing `Applying ...sql`
followed by a `psql` error means that migration failed; later files will not
have run. In Cloud SQL Studio, connect to `mealshopper_shopper` as an
administrator and inspect the role and created objects with:

```sql
SELECT rolname FROM pg_roles WHERE rolname IN ('shopper_app', 'users_app');
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
```

The Shopper's `00_init/01_init_databases.sql` is a placeholder containing no
active statements. The `shopper_app` role and databases are created by
Terraform; the later SQL files create the Shopper schema objects.

## Local Docker credentials

Copy `.env.example` to `.env`, replace every password placeholder with a
different generated value, and keep `.env` out of source control. Docker
Compose uses those values both to initialize the local PostgreSQL roles and to
configure each service. The PostgreSQL initialization scripts run only when
the data volume is first created; after rotating local credentials on an
existing volume, update the role passwords in PostgreSQL as well.

## Publish the static frontend

Build the Vite app without `VITE_API_GATEWAY_URL` to use the same-origin `/v1`
path routed by the load balancer, then upload the contents of `dist` to
`web_bucket_name`:

```powershell
npm --prefix apps/mealshopper-web run build
gcloud storage rsync --recursive apps/mealshopper-web/dist gs://<web_bucket_name>
```

Create a DNS A record for `frontend_domain` pointing to Terraform's
`frontend_ip_address` output. Google-managed certificate provisioning may take
time after DNS resolves.

## Scope and follow-up

The configured Cloud Run services are the orchestrator, API gateway, Identity,
Users, planning, and shopper APIs; the web UI is static content on the HTTPS
load balancer.
