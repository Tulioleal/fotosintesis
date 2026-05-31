resource "google_monitoring_notification_channel" "email" {
  count        = var.notification_email == "" ? 0 : 1
  project      = var.project_id
  display_name = "Fotosintesis alerts"
  type         = "email"

  labels = {
    email_address = var.notification_email
  }
}

resource "google_monitoring_alert_policy" "cluster_cpu" {
  project      = var.project_id
  display_name = "Fotosintesis GKE high CPU allocation"
  combiner     = "OR"

  conditions {
    display_name = "GKE CPU allocation above threshold"

    condition_threshold {
      filter          = "resource.type=\"k8s_node\" AND metric.type=\"kubernetes.io/node/cpu/allocatable_utilization\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.cpu_threshold

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [for channel in google_monitoring_notification_channel.email : channel.name]
}
