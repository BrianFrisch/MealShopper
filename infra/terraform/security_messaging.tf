resource "google_pubsub_topic" "meal_plan_tasks" {
  name    = "meal-plan-tasks"
  project = var.project_id

  depends_on = [google_project_service.required_apis["pubsub.googleapis.com"]]
}

resource "google_pubsub_subscription" "meal_plan_tasks" {
  name    = "meal-plan-tasks-pull"
  topic   = google_pubsub_topic.meal_plan_tasks.id
  project = var.project_id
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "mealshopper-db-password"
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

resource "google_secret_manager_secret_iam_member" "db_password_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_pubsub_topic_iam_member" "meal_plan_tasks_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.meal_plan_tasks.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_pubsub_subscription_iam_member" "meal_plan_tasks_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.meal_plan_tasks.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_storage_bucket_iam_member" "worker_file_admin" {
  bucket = google_storage_bucket.worker_files.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}
