variable "project_id" {
  description = "GCP Project ID to monitor"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "billing_dataset_location" {
  description = "Location for BigQuery billing dataset"
  type        = string
  default     = "US"
}

variable "service_account_name" {
  description = "Name for CloudGuard service account"
  type        = string
  default     = "cloudguard-agent"
}

variable "billing_dataset_name" {
  description = "BigQuery dataset name for billing export"
  type        = string
  default     = "billing_export"
}

variable "audit_dataset_name" {
  description = "BigQuery dataset name for audit logs"
  type        = string
  default     = "cloudguard_audit"
}
