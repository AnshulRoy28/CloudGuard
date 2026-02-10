# Enable required APIs
resource "google_project_service" "bigquery" {
  project = var.project_id
  service = "bigquery.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "compute" {
  project = var.project_id
  service = "compute.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  project = var.project_id
  service = "storage-api.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "logging" {
  project = var.project_id
  service = "logging.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "cloudscheduler" {
  project = var.project_id
  service = "cloudscheduler.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "run" {
  project = var.project_id
  service = "run.googleapis.com"
  
  disable_on_destroy = false
}

# BigQuery dataset for billing export
resource "google_bigquery_dataset" "billing_export" {
  dataset_id = var.billing_dataset_name
  location   = var.billing_dataset_location
  
  description = "CloudGuard AI - Billing export dataset"
  
  labels = {
    managed_by = "cloudguard"
    purpose    = "billing_export"
  }
  
  depends_on = [google_project_service.bigquery]
}

# BigQuery dataset for audit logs
resource "google_bigquery_dataset" "audit" {
  dataset_id = var.audit_dataset_name
  location   = var.billing_dataset_location
  
  description = "CloudGuard AI - Audit logs dataset"
  
  labels = {
    managed_by = "cloudguard"
    purpose    = "audit_logs"
  }
  
  depends_on = [google_project_service.bigquery]
}

# Audit log table
resource "google_bigquery_table" "audit_log" {
  dataset_id = google_bigquery_dataset.audit.dataset_id
  table_id   = "action_history"
  
  description = "CloudGuard action audit trail"
  
  schema = jsonencode([
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "project_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "resource_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "action"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "estimated_savings"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "result_status"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "user_email"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "token_issued_at"
      type = "TIMESTAMP"
      mode = "NULLABLE"
    }
  ])
}
