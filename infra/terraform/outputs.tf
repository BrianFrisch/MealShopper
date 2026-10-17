output "orchestrator_uri" {
  description = "URI of the MealShopper C# API orchestrator Cloud Run service."
  value       = google_cloud_run_v2_service.orchestrator.uri
}

output "planning_domain_uri" {
  description = "Private URI of the MealShopper Python planning service."
  value       = google_cloud_run_v2_service.planning_domain.uri
}

output "shopper_domain_uri" {
  description = "Private URI of the MealShopper Python shopper service."
  value       = google_cloud_run_v2_service.shopper_domain.uri
}

output "identity_uri" {
  description = "Private URI of the MealShopper identity service."
  value       = google_cloud_run_v2_service.identity.uri
}

output "user_service_uri" {
  description = "Private URI of the MealShopper user service."
  value       = google_cloud_run_v2_service.user_service.uri
}

output "api_gateway_uri" {
  description = "Cloud Run URI of the API gateway; external traffic should use the HTTPS load balancer."
  value       = google_cloud_run_v2_service.api_gateway.uri
}

output "frontend_url" {
  description = "HTTPS URL for the MealShopper web frontend and API."
  value       = "https://${var.frontend_domain}"
}

output "frontend_ip_address" {
  description = "Global IP address to point the frontend domain DNS A record to."
  value       = google_compute_global_address.web.address
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository path for MealShopper service images."
  value       = "us-west1-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mealshopper.repository_id}"
}
