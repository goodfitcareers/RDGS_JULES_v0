
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Use the .env.example values as default for better out-of-the-box behavior for tools
    # if .env file is not present.
    # Changed to use psycopg3 dialect connector
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/dataset_distiller_db"
    )
    OPENAI_API_KEY: str = "your_openai_api_key_here"
    OPENAI_MODEL_NAME: str = "gpt-4-turbo"  # Or your preferred model
    NOTION_CLIENT_ID: str = "your_notion_client_id_here"
    NOTION_CLIENT_SECRET: str = "your_notion_client_secret_here"
    # Add other settings as needed later
    LANGSMITH_PROJECT: str = "DatasetDistiller"
    LANGCHAIN_TRACING_V2: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Or "forbid" if you want to be strict


settings = Settings()
