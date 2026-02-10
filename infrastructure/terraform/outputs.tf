output "service_account_email" {
  description = "Email of the CloudGuard service account"
  value       = google_service_account.cloudguard.email
}

output "service_account_key_file" {
  description = "Path to the service account key file"
  value       = local_file.service_account_key.filename
  sensitive   = true
}

output "billing_dataset_id" {
  description = "BigQuery billing export dataset ID"
  value       = google_bigquery_dataset.billing_export.dataset_id
}

output "audit_dataset_id" {
  description = "BigQuery audit logs dataset ID"
  value       = google_bigquery_dataset.audit.dataset_id
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "next_steps" {
  description = "Next steps after Terraform deployment"
  value = <<-EOT
  
  ✅ Terraform deployment complete!
  
  Next steps:
  1. Configure billing export in GCP Console:
     - Go to: https://console.cloud.google.com/billing
     - Click: Billing Export → BigQuery Export
     - Dataset: ${google_bigquery_dataset.billing_export.dataset_id}
     
  2. Run the setup wizard:
     python scripts/setup.py
     
  3. The setup wizard will help you:
     - Get SendGrid API key
     - Get Gemini API key
     - Configure budget thresholds
     - Generate .env file
     - Validate the setup
  
  Service Account: ${google_service_account.cloudguard.email}
  Key File: ${local_file.service_account_key.filename}
  EOT
}
