resource "google_secret_manager_secret" "db_password" {
  secret_id = "mealshopper-db-password"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "users_db_password" {
  secret_id = "mealshopper-users-db-password"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "shopper_db_password" {
  secret_id = "mealshopper-shopper-db-password"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "planner_db_password" {
  secret_id = "mealshopper-planner-db-password"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "orchestrator_client_secret" {
  secret_id = "mealshopper-orchestrator-client-secret"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "jwt_signing_key" {
  secret_id = "mealshopper-jwt-signing-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "mealshopper-gemini-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis["secretmanager.googleapis.com"]]
}

resource "google_service_account" "cloud_run" {
  account_id   = "mealshopper-cr-sa"
  display_name = "MealShopper Cloud Run service account"
  project      = var.project_id
}

resource "google_secret_manager_secret_iam_member" "runtime_secrets" {
  for_each = {
    users_db_password          = google_secret_manager_secret.users_db_password.secret_id
    shopper_db_password        = google_secret_manager_secret.shopper_db_password.secret_id
    planner_db_password        = google_secret_manager_secret.planner_db_password.secret_id
    orchestrator_client_secret = google_secret_manager_secret.orchestrator_client_secret.secret_id
    jwt_signing_key            = google_secret_manager_secret.jwt_signing_key.secret_id
    gemini_api_key             = google_secret_manager_secret.gemini_api_key.secret_id
  }

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_storage_bucket_iam_member" "worker_file_admin" {
  bucket = google_storage_bucket.worker_files.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}
