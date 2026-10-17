resource "google_artifact_registry_repository" "mealshopper" {
  location      = "us-west1"
  repository_id = "mealshopper"
  description   = "Docker images for MealShopper services"
  format        = "DOCKER"
  project       = var.project_id

  depends_on = [google_project_service.required_apis["artifactregistry.googleapis.com"]]
}

resource "google_cloud_run_v2_service" "orchestrator" {
  name                = "mealshopper-orchestrator"
  location            = "us-west1"
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection

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
      ports {
        container_port = 5277
      }

      env {
        name  = "ConnectionStrings__Redis"
        value = "${google_redis_instance.mealshopper.host}:${google_redis_instance.mealshopper.port}"
      }
      env {
        name  = "Services__ShopperDomainUrl"
        value = google_cloud_run_v2_service.shopper_domain.uri
      }
      env {
        name  = "Services__PlanningDomainUrl"
        value = google_cloud_run_v2_service.planning_domain.uri
      }
      env {
        name  = "Identity__TokenEndpoint"
        value = "${google_cloud_run_v2_service.identity.uri}/v1/auth/token"
      }
      env {
        name = "Identity__ClientSecret"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.orchestrator_client_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_secret_manager_secret_iam_member.runtime_secrets,
  ]
}

resource "google_cloud_run_v2_service" "identity" {
  name                = "mealshopper-identity"
  location            = "us-west1"
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection

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
      image = var.identity_image
      ports {
        container_port = 5119
      }

      env {
        name  = "Identity__Audience"
        value = "mealshopper-api"
      }
      env {
        name = "Jwt__SigningKey"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_signing_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "UserService__BaseUrl"
        value = google_cloud_run_v2_service.user_service.uri
      }
      env {
        name  = "ConnectionStrings__Redis"
        value = "${google_redis_instance.mealshopper.host}:${google_redis_instance.mealshopper.port}"
      }
      env {
        name = "Clients__Orchestrator__ClientSecret"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.orchestrator_client_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_secret_manager_secret_iam_member.runtime_secrets,
  ]
}

resource "google_cloud_run_v2_service" "user_service" {
  name                = "mealshopper-users"
  location            = "us-west1"
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection

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
      image = var.user_service_image
      ports {
        container_port = 5125
      }

      env {
        name  = "POSTGRES_HOST"
        value = google_sql_database_instance.mealshopper.private_ip_address
      }
      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }
      env {
        name  = "POSTGRES_DB"
        value = google_sql_database.user_service.name
      }
      env {
        name  = "POSTGRES_USER"
        value = google_sql_user.users_app.name
      }
      env {
        name = "POSTGRES_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.users_db_password.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_secret_manager_secret_iam_member.runtime_secrets,
    google_sql_user.users_app,
  ]
}

resource "google_cloud_run_v2_service" "planning_domain" {
  name                = "mealshopper-planning"
  location            = "us-west1"
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection

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
      image = var.planning_domain_image
      ports {
        container_port = 8002
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GEMINI_MODEL_NAME"
        value = var.gemini_model_name
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_secret_manager_secret_iam_member.runtime_secrets,
  ]
}

resource "google_cloud_run_v2_service" "shopper_domain" {
  name                = "mealshopper-shopper"
  location            = "us-west1"
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection

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
      image = var.shopper_domain_image
      ports {
        container_port = 8001
      }

      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.mealshopper.host}:${google_redis_instance.mealshopper.port}"
      }
      env {
        name  = "POSTGRES_HOST"
        value = google_sql_database_instance.mealshopper.private_ip_address
      }
      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }
      env {
        name  = "POSTGRES_DB"
        value = google_sql_database.shopper_domain.name
      }
      env {
        name  = "POSTGRES_USER"
        value = google_sql_user.shopper_app.name
      }
      env {
        name = "POSTGRES_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.shopper_db_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "DEAL_DATA_DIR"
        value = "/tmp/deals"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_secret_manager_secret_iam_member.runtime_secrets,
    google_storage_bucket_iam_member.worker_file_admin,
    google_sql_user.shopper_app,
  ]
}

resource "google_cloud_run_v2_service" "api_gateway" {
  name                = "mealshopper-api-gateway"
  location            = "us-west1"
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = var.cloud_run_deletion_protection

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
      image = var.gateway_image
      ports {
        container_port = 5247
      }

      env {
        name  = "Identity__Authority"
        value = google_cloud_run_v2_service.identity.uri
      }
      env {
        name  = "Identity__Audience"
        value = "mealshopper-api"
      }
      env {
        name  = "Identity__RequireHttpsMetadata"
        value = "true"
      }
      env {
        name  = "Cors__AllowedOrigins__0"
        value = "https://${var.frontend_domain}"
      }
      env {
        name  = "ReverseProxy__Clusters__identityCluster__Destinations__destination1__Address"
        value = google_cloud_run_v2_service.identity.uri
      }
      env {
        name  = "ReverseProxy__Clusters__orchestrator-cluster__Destinations__destination1__Address"
        value = google_cloud_run_v2_service.orchestrator.uri
      }
      env {
        name  = "ReverseProxy__Clusters__users-cluster__Destinations__destination1__Address"
        value = google_cloud_run_v2_service.user_service.uri
      }
      env {
        name  = "ReverseProxy__Clusters__shopperCluster__Destinations__destination1__Address"
        value = google_cloud_run_v2_service.shopper_domain.uri
      }
    }
  }

  depends_on = [
    google_project_service.required_apis["run.googleapis.com"],
    google_cloud_run_v2_service_iam_member.private_service_invoker,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "private_service_invoker" {
  for_each = {
    orchestrator = google_cloud_run_v2_service.orchestrator.name
    identity     = google_cloud_run_v2_service.identity.name
    user_service = google_cloud_run_v2_service.user_service.name
    planning     = google_cloud_run_v2_service.planning_domain.name
    shopper      = google_cloud_run_v2_service.shopper_domain.name
  }

  project  = var.project_id
  location = "us-west1"
  name     = each.value
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_cloud_run_v2_service_iam_member" "gateway_invoker" {
  project  = var.project_id
  location = "us-west1"
  name     = google_cloud_run_v2_service.api_gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_storage_bucket" "web_assets" {
  name                        = var.web_bucket_name
  location                    = "US-WEST1"
  project                     = var.project_id
  uniform_bucket_level_access = true
  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }
}

resource "google_storage_bucket_iam_member" "web_public_viewer" {
  bucket = google_storage_bucket.web_assets.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_compute_backend_bucket" "web_assets" {
  name        = "mealshopper-web-assets"
  bucket_name = google_storage_bucket.web_assets.name
  enable_cdn  = true
}

resource "google_compute_region_network_endpoint_group" "api_gateway" {
  name                  = "mealshopper-gateway-neg"
  region                = "us-west1"
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api_gateway.name
  }
}

resource "google_compute_backend_service" "api_gateway" {
  name                  = "mealshopper-gateway-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"

  backend {
    group = google_compute_region_network_endpoint_group.api_gateway.id
  }
}

resource "google_compute_url_map" "https" {
  name            = "mealshopper-https"
  default_service = google_compute_backend_bucket.web_assets.id

  host_rule {
    hosts        = [var.frontend_domain]
    path_matcher = "mealshopper-routes"
  }

  path_matcher {
    name            = "mealshopper-routes"
    default_service = google_compute_backend_bucket.web_assets.id

    path_rule {
      paths   = ["/v1", "/v1/*"]
      service = google_compute_backend_service.api_gateway.id
    }
  }
}

resource "google_compute_managed_ssl_certificate" "web" {
  name = "mealshopper-web-cert"

  managed {
    domains = [var.frontend_domain]
  }
}

resource "google_compute_target_https_proxy" "web" {
  name             = "mealshopper-https-proxy"
  url_map          = google_compute_url_map.https.id
  ssl_certificates = [google_compute_managed_ssl_certificate.web.id]
}

resource "google_compute_global_address" "web" {
  name = "mealshopper-web-ip"
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "mealshopper-https-forwarding-rule"
  target                = google_compute_target_https_proxy.web.id
  ip_address            = google_compute_global_address.web.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_url_map" "http_redirect" {
  name = "mealshopper-http-redirect"

  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
  }
}

resource "google_compute_target_http_proxy" "web_redirect" {
  name    = "mealshopper-http-proxy"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "mealshopper-http-forwarding-rule"
  target                = google_compute_target_http_proxy.web_redirect.id
  ip_address            = google_compute_global_address.web.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
