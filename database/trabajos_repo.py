from database.supabase_client import get_supabase_client

class TrabajosRepo:

    def __init__(self):
        self.supabase = get_supabase_client()

    def crear_trabajo(self, documento_id: str, tipo: str) -> str:
        """Crea un nuevo trabajo de indexación y devuelve su job_id."""
        response = self.supabase.table("trabajos_indexacion").insert({
            "documento_id": documento_id,
            "tipo": tipo,
            "estado": "en_proceso",
            "progreso": "Iniciando pipeline..."
        }).execute()
        return response.data[0]["id_job"]

    def actualizar_progreso(self, job_id: str, progreso: str) -> None:
        self.supabase.table("trabajos_indexacion") \
            .update({"progreso": progreso}) \
            .eq("id_job", job_id) \
            .execute()

    def completar(self, job_id: str) -> None:
        self.supabase.table("trabajos_indexacion") \
            .update({
                "estado": "completado",
                "progreso": "Indexación completada.",
                "fecha_fin": "now()"
            }) \
            .eq("id_job", job_id) \
            .execute()

    def marcar_error(self, job_id: str, mensaje_error: str) -> None:
        self.supabase.table("trabajos_indexacion") \
            .update({
                "estado": "error",
                "progreso": "El proceso falló.",
                "mensaje_error": mensaje_error,
                "fecha_fin": "now()"
            }) \
            .eq("id_job", job_id) \
            .execute()

    def obtener(self, job_id: str) -> dict | None:
        response = self.supabase.table("trabajos_indexacion") \
            .select("id_job, documento_id, tipo, estado, progreso, mensaje_error, fecha_inicio, fecha_fin") \
            .eq("id_job", job_id) \
            .execute()
        return response.data[0] if response.data else None