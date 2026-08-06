import hashlib
from database.supabase_client import get_supabase_client


class DocumentosRepo:

    def __init__(self):
        self.supabase = get_supabase_client()

    @staticmethod
    def calcular_hash(texto: str) -> str:
        """Hash sobre el texto YA extraído y limpio, no sobre los bytes
        crudos del PDF. Evita falsos 'documento nuevo' cuando el mismo
        PDF se re-sube reexportado con metadata distinta pero mismo contenido."""
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()

    def existe_hash(self, hash_contenido: str) -> bool:
        response = self.supabase.table("documentos") \
            .select("id_documento") \
            .eq("hash_contenido", hash_contenido) \
            .execute()
        return len(response.data) > 0

    def obtener_por_id(self, documento_id: str) -> dict | None:
        response = self.supabase.table("documentos") \
            .select("id_documento, nombre_archivo, hash_contenido, estado, fecha_carga, version") \
            .eq("id_documento", documento_id) \
            .execute()
        return response.data[0] if response.data else None

    def listar(self) -> list:
        response = self.supabase.table("documentos") \
            .select("id_documento, nombre_archivo, fecha_carga, estado, version") \
            .order("fecha_carga", desc=True) \
            .execute()
        return response.data

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

    def actualizar_tras_reproceso(self, documento_id: str, nuevo_hash: str) -> None:
        """Actualiza hash y versión tras una actualización exitosa de documento."""
        doc = self.obtener_por_id(documento_id)
        nueva_version = (doc["version"] + 1) if doc else 1
        self.supabase.table("documentos") \
            .update({
                "hash_contenido": nuevo_hash,
                "version": nueva_version,
                "estado": "indexado"
            }) \
            .eq("id_documento", documento_id) \
            .execute()

    def eliminar_documento(self, documento_id: str) -> None:
        """Borra el documento. La cascada en BD limpia chunks_padres
        y chunks_hijos automáticamente."""
        self.supabase.table("documentos") \
            .delete() \
            .eq("id_documento", documento_id) \
            .execute()

    def eliminar_chunks(self, documento_id: str) -> None:
        """Borra solo los chunks_padres de un documento (cascada a hijos).
        Se usa en el swap atómico del PUT para reemplazar chunks viejos
        por nuevos sin borrar el documento en sí."""
        self.supabase.table("chunks_padres") \
            .delete() \
            .eq("documento_id", documento_id) \
            .execute()