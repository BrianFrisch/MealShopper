terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = "us-west1"
}

locals {
  required_apis = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "servicenetworking.googleapis.com",
  ])
}

resource "google_project_service" "required_apis" {
  for_each = local.required_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "mealshopper" {
  name                    = "mealshopper-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id

  depends_on = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "mealshopper" {
  name          = "mealshopper-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = "us-west1"
  network       = google_compute_network.mealshopper.id
  project       = var.project_id
}

resource "google_compute_global_address" "private_service_access" {
  name          = "mealshopper-private-service-access"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.mealshopper.id
  project       = var.project_id
}

resource "google_service_networking_connection" "private_service_access" {
  network                 = google_compute_network.mealshopper.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]

  depends_on = [google_project_service.required_apis]
}
