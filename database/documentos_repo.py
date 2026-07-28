import hashlib
from database.supabase_client import get_supabase_client


class DocumentosRepo:

    def __init__(self):
        self.supabase = get_supabase_client()

    @staticmethod
    def calcular_hash(texto: str) -> str:
        """Hash sobre el texto YA extraído y limpio, no sobre los bytes
        crudos del PDF. Esto evita falsos 'documento nuevo' cuando el
        mismo PDF se re-sube reexportado por otra herramienta (metadata
        binaria distinta, mismo contenido semántico)."""
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()

    def existe_hash(self, hash_contenido: str) -> bool:
        response = self.supabase.table("documentos") \
            .select("id_documento") \
            .eq("hash_contenido", hash_contenido) \
            .execute()
        return len(response.data) > 0

    def crear_documento(self, nombre_archivo: str, hash_contenido: str) -> str:
        response = self.supabase.table("documentos").insert({
            "nombre_archivo": nombre_archivo,
            "hash_contenido": hash_contenido,
            "estado": "pendiente"
        }).execute()
        return response.data[0]["id_documento"]

    def actualizar_estado(self, documento_id: str, estado: str) -> None:
        self.supabase.table("documentos") \
            .update({"estado": estado}) \
            .eq("id_documento", documento_id) \
            .execute()

    def eliminar_documento(self, documento_id: str) -> None:
        """Borra el documento. La cascada en BD limpia automáticamente
        cualquier chunk_padre/chunk_hijo huérfano si el pipeline falló
        a medio camino, sin necesidad de borrarlos manualmente."""
        self.supabase.table("documentos") \
            .delete() \
            .eq("id_documento", documento_id) \
            .execute()