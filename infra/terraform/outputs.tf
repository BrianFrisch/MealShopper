output "orchestrator_uri" {
  description = "URI of the MealShopper C# API orchestrator Cloud Run service."
  value       = google_cloud_run_v2_service.orchestrator.uri
}

output "agent_worker_uri" {
  description = "URI of the MealShopper Python agent worker Cloud Run service."
  value       = google_cloud_run_v2_service.agent_worker.uri
}
