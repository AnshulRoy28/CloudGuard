# Service account for CloudGuard
resource "google_service_account" "cloudguard" {
  account_id   = var.service_account_name
  display_name = "CloudGuard AI Agent"
  description  = "Service account for CloudGuard AI autonomous FinOps agent"
}

# IAM roles for BigQuery
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloudguard.email}"
}

resource "google_project_iam_member" "bigquery_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.cloudguard.email}"
}

# IAM roles for Compute Engine
resource "google_project_iam_member" "compute_instance_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.cloudguard.email}"
}

# IAM role for Cloud Storage
resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.cloudguard.email}"
}

# IAM role for Logging
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloudguard.email}"
}

# Custom IAM role with minimal permissions (optional, more secure)
resource "google_project_iam_custom_role" "cloudguard_minimal" {
  role_id     = "cloudguardMinimal"
  title       = "CloudGuard Minimal Permissions"
  description = "Minimal permissions required for CloudGuard AI"
  
  permissions = [
    "bigquery.jobs.create",
    "bigquery.tables.get",
    "bigquery.tables.getData",
    "compute.instances.get",
    "compute.instances.stop",
    "compute.snapshots.create",
    "storage.buckets.get",
    "storage.buckets.update",
    "logging.logEntries.create"
  ]
}

# Service account key (for local development)
# NOTE: In production, use Workload Identity instead
resource "google_service_account_key" "cloudguard_key" {
  service_account_id = google_service_account.cloudguard.name
}

# Save the key to a local file
resource "local_file" "service_account_key" {
  content         = base64decode(google_service_account_key.cloudguard_key.private_key)
  filename        = "${path.module}/../../cloudguard-sa-key.json"
  file_permission = "0600"
}
