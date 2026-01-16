variable "production" {
  description = "Wether to deploy in production mode"
  type        = bool
  default     = true
}

variable "region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "dyno-agent"
}

variable "db_password" {
  description = "Postgres Database Password"
  type        = string
  sensitive   = true
}

variable "huggingface_token" {
  description = "HuggingFace API Token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Gemini API Key"
  type        = string
  sensitive   = true
  default     = ""
} 

variable "jwt_secret" {
  description = "JWT Secret Key"
  type        = string
  sensitive   = true
  default     = "change-me-in-production"
}

variable "backup_retention_days" {
  description = "Number of days to retain database backups (7 for dev, 30 for production)"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "Preferred backup window (UTC). Format: HH:MM-HH:MM"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window (UTC). Format: ddd:HH:MM-ddd:HH:MM"
  type        = string
  default     = "sun:04:00-sun:05:00"
}
