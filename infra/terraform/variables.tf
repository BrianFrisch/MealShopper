variable "project_id" {
  description = "Google Cloud project ID where MealShopper infrastructure will be created."
  type        = string
}

variable "subnet_cidr" {
  description = "IPv4 CIDR range for mealshopper-subnet; must not overlap other VPC ranges."
  type        = string
  default     = "10.10.0.0/24"
}

variable "sql_password" {
  description = "Password for the PostgreSQL administrator user. Supply through a secure Terraform variable source."
  type        = string
  sensitive   = true
}

variable "users_db_password" {
  description = "Password for the Users service PostgreSQL role; must match the mealshopper-users-db-password Secret Manager version."
  type        = string
  sensitive   = true
}

variable "shopper_db_password" {
  description = "Password for the Shopper service PostgreSQL role; must match the mealshopper-shopper-db-password Secret Manager version."
  type        = string
  sensitive   = true
}

variable "sql_tier" {
  description = "Cloud SQL machine tier. db-f1-micro is the lowest-cost shared-core tier, but is not an always-free tier."
  type        = string
  default     = "db-f1-micro"
}

variable "redis_tier" {
  description = "Memorystore for Redis service tier."
  type        = string
  default     = "BASIC"
}

variable "redis_memory_size_gb" {
  description = "Memorystore for Redis memory size in GiB."
  type        = number
  default     = 1
}

variable "worker_bucket_name" {
  description = "Globally unique Cloud Storage bucket name for Python worker files."
  type        = string
}

variable "orchestrator_image" {
  description = "Container image URI for the C# API orchestrator."
  type        = string
}

variable "planning_domain_image" {
  description = "Container image URI for the Python planning API."
  type        = string
}

variable "shopper_domain_image" {
  description = "Container image URI for the Python shopper API."
  type        = string
}

variable "user_service_image" {
  description = "Container image URI for the C# user service."
  type        = string
}

variable "identity_image" {
  description = "Container image URI for the C# identity service."
  type        = string
}

variable "gateway_image" {
  description = "Container image URI for the API gateway."
  type        = string
}

variable "gemini_model_name" {
  description = "Gemini model used by the planning domain."
  type        = string
  default     = "gemini-3.8-flash"
}

variable "web_bucket_name" {
  description = "Globally unique Cloud Storage bucket name for the public web frontend."
  type        = string
}

variable "frontend_domain" {
  description = "DNS name served by the static frontend and HTTPS load balancer."
  type        = string
}

variable "cloud_run_deletion_protection" {
  description = "Prevent accidental deletion of Cloud Run services. Disable and apply before destroying services."
  type        = bool
  default     = true
}

variable "sql_deletion_protection" {
  description = "Prevent accidental deletion of the Cloud SQL instance. Disable and apply before destroying it."
  type        = bool
  default     = true
}
