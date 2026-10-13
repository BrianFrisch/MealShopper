resource "google_artifact_registry_repository" "mealshopper" {
  location      = "us-west1"
  repository_id = "mealshopper"
  description   = "Docker images for MealShopper services"
  format        = "DOCKER"
  project       = var.project_id

  depends_on = [google_project_service.required_apis["artifactregistry.googleapis.com"]]
}

resource "google_cloud_run_v2_service" "orchestrator" {
  name     = "mealshopper-orchestrator"
  location = "us-west1"
  project  = var.project_id

  template {
    service_account = google_service_account.cloud_run.email

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"

      network_interfaces {
        network    = google_compute_network.mealshopper.id
        subnetwork = google_compute_subnetwork.mealshopper.id
      }
    }

    containers {
      image = var.orchestrator_image

      env {
        name = "POSTGRES_PASSWORD"

        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_secret_manager_secret_iam_member.db_password_accessor,
  ]
}

resource "google_cloud_run_v2_service" "agent_worker" {
  name     = "mealshopper-agent-worker"
  location = "us-west1"
  project  = var.project_id

  template {
    service_account = google_service_account.cloud_run.email

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"

      network_interfaces {
        network    = google_compute_network.mealshopper.id
        subnetwork = google_compute_subnetwork.mealshopper.id
      }
    }

    containers {
      image = var.agent_worker_image
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_storage_bucket_iam_member.worker_file_admin,
    google_pubsub_subscription_iam_member.meal_plan_tasks_subscriber,
  ]
}
