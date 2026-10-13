resource "google_sql_database_instance" "mealshopper" {
  name                = "mealshopper-postgres"
  database_version    = "POSTGRES_16"
  region              = "us-west1"
  deletion_protection = true

  settings {
    tier = var.sql_tier

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.mealshopper.self_link
    }
  }

  depends_on = [google_service_networking_connection.private_service_access]
}

resource "google_sql_database" "mealshopper" {
  name     = "mealshopper"
  instance = google_sql_database_instance.mealshopper.name
}

resource "google_sql_user" "default" {
  name     = "postgres"
  instance = google_sql_database_instance.mealshopper.name
  password = var.sql_password
}

resource "google_redis_instance" "mealshopper" {
  name           = "mealshopper-redis"
  region         = "us-west1"
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_size_gb

  authorized_network = google_compute_network.mealshopper.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  depends_on = [google_service_networking_connection.private_service_access]
}

resource "google_storage_bucket" "worker_files" {
  name                        = var.worker_bucket_name
  location                    = "US-WEST1"
  project                     = var.project_id
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.required_apis["storage.googleapis.com"]]
}

resource "google_firestore_database" "mealshopper" {
  project     = var.project_id
  name        = "(default)"
  location_id = "us-west1"
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.required_apis["firestore.googleapis.com"]]
}
