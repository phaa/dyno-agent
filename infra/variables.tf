variable "region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "dyno-agent"
}

variable "db_password" {
  description = "Senha do Postgres"
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
