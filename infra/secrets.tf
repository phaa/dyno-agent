resource "aws_secretsmanager_secret" "api" {
  name = "${var.project_name}-secrets"
}

resource "aws_secretsmanager_secret_version" "api" {
  secret_id = aws_secretsmanager_secret.api.id

  secret_string = jsonencode({
    PRODUCTION = var.production
    
    HUGGING_FACE_HUB_TOKEN = var.huggingface_token
    GEMINI_API_KEY         = var.gemini_api_key

    # SQLAlchemy - asyncpg driver
    DATABASE_URL_PROD = "postgresql+asyncpg://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}"
    
    # LangGraph Checkpointer - psycopg2 driver
    DATABASE_URL_CHECKPOINTER_PROD = "postgresql://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}?sslmode=require"
    
    POSTGRES_USER     = aws_db_instance.postgres.username
    POSTGRES_PASSWORD = var.db_password
    POSTGRES_DB       = aws_db_instance.postgres.db_name

    JWT_SECRET            = var.jwt_secret
    JWT_ALGORITHM         = "HS256"
    JWT_EXP_DELTA_SECONDS = "3600"
  })
}
