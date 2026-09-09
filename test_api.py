import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

for model in ["gemini-embedding-2", "gemini-embedding-001", "gemini-embedding-2-preview"]:
    try:
        result = client.models.embed_content(model=model, contents=["login page spinner hangs forever"])
        dim = len(result.embeddings[0].values)
        print(f"OK  {model}  dim={dim}")
    except Exception as e:
        print(f"FAIL {model}: {str(e)[:80]}")
