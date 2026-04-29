import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "federhub-super-secret-key-change-in-production")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
