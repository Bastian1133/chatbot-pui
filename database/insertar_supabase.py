from database.supabase_client import get_supabase_client
from datetime import date

class InsersorSupabase:

    def __init__(self):
        self.supabase = get_supabase_client()

    def insertar_bloques(self, bloques: list, embeddings: list, documento_id: str) -> None:
        embedding_idx = 0

        for bloque in bloques:
            # Insertar padre, vinculado al documento del que proviene
            response = self.supabase.table("chunks_padres").insert({
                "contexto_completo": bloque["padre"]["contexto_completo"],
                "fuente": bloque["padre"]["fuente"],
                "documento_id": documento_id,
                "fecha_indexacion": date.today().isoformat()
            }).execute()

            padre_id = response.data[0]["id_chunk_padre"]
            print(f"  Padre insertado — id: {padre_id}")

            # Insertar hijos con sus embeddings
            for hijo in bloque["hijos"]:
                self.supabase.table("chunks_hijos").insert({
                    "padre_id": padre_id,
                    "texto_embedding": hijo["texto_embedding"],
                    "embedding": embeddings[embedding_idx]
                }).execute()
                embedding_idx += 1

            print(f"  Hijos insertados: {len(bloque['hijos'])}")