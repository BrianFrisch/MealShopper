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
  description = "Password for the default PostgreSQL user. Supply through a secure Terraform variable source."
  type        = string
  sensitive   = true
}

variable "sql_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-custom-1-3840"
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

variable "agent_worker_image" {
  description = "Container image URI for the Python agent worker."
  type        = string
}
