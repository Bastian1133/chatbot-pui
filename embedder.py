import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv(Path(__file__).parent / "keys.env") # Carga las variables de entorno desde el archivo keys.env

class Embedder:
    
    def __init__(self):

        # Decodificar las credenciales desde la variable de entorno
        service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
        if not service_account_info:
            raise ValueError("Falta GOOGLE_SERVICE_ACCOUNT_JSON en el archivo keys.env")

        # Asignar el scope de Cloud Platform
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, 
            scopes=scopes  # <--- Asigna los permisos OAuth requeridos
        )

        project_id = os.getenv("PROJECT_ID")
        if not project_id:
            raise ValueError("Falta PROJECT_ID en el archivo keys.env")
        
        self.modelo = GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",
            vertexai=True,
            project=project_id,
            credentials=credentials,
            location="us-east4",
            output_dimensionality=768
        )
    
    def vectorizar_consulta(self, texto: str) -> list:
        return self.modelo.embed_query(texto)
    
    def vectorizar_lote(self, textos: list, batch_size: int = 20) -> list:
        embeddings = []
        total = len(textos)

        for i in range(0, total, batch_size):
            lote = textos[i:i + batch_size]
            resultados = self.modelo.embed_documents(lote)
            embeddings.extend(resultados)
            print(f"  Vectorizados {min(i + batch_size, total)}/{total}...")

            if i + batch_size < total:
                time.sleep(3)  # Defensivo, no por necesidad real

        return embeddings