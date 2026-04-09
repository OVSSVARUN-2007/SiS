import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

HF_API_KEY = os.getenv("HF_API_KEY")

print(HF_API_KEY)  # Just to test