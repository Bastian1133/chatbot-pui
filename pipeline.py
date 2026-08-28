import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from indexador.segmentador import Segmentador
from indexador.chunker import Chunker
from embedder import Embedder
from database.insertar_supabase import InsersorSupabase
from database.documentos_repo import DocumentosRepo
from database.trabajos_repo import TrabajosRepo

"""
Pipeline de indexación reutilizable.

Contiene la lógica que corre en background tanto para alta
(POST /documentos) como para actualización (PUT /documentos/{id}).
Separarlo de app.py permite reutilizarlo sin duplicar código y
facilita la migración al script local de indexación.
"""

# Instancias compartidas — se inicializan una vez al importar el módulo
_segmentador = None
_chunker = None
_embedder = None


def _get_segmentador():
    global _segmentador
    if _segmentador is None:
        _segmentador = Segmentador()
    return _segmentador


def _get_chunker():
    global _chunker
    if _chunker is None:
        _chunker = Chunker()
    return _chunker


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def pipeline_alta(documento_id: str, job_id: str, nombre_archivo: str, texto: str):
    """
    Pipeline completo para un documento nuevo.
    Corre en background tras POST /documentos.
    Si falla en cualquier punto: borra el documento (cascada limpia chunks)
    y marca el job como error.
    """
    docs_repo = DocumentosRepo()
    trabajos_repo = TrabajosRepo()
    insersor = InsersorSupabase()

    try:
        # Etapa 1: segmentación temática
        trabajos_repo.actualizar_progreso(job_id, "Segmentando documento con Gemini...")
        bloques_texto = _get_segmentador().segmentar(texto)
        total_bloques = len(bloques_texto)

        # Etapa 2: chunking
        trabajos_repo.actualizar_progreso(job_id, f"Generando chunks ({total_bloques} bloques temáticos)...")
        bloques = _get_chunker().generar_chunks_desde_bloques(bloques_texto, nombre_archivo)

        textos_hijos = [
            hijo["texto_embedding"]
            for bloque in bloques
            for hijo in bloque["hijos"]
        ]
        total_hijos = len(textos_hijos)

        # Etapa 3: embeddings (el más lento — respeta rate limit de Gemini)
        trabajos_repo.actualizar_progreso(job_id, f"Vectorizando {total_hijos} fragmentos...")
        embeddings = _get_embedder().vectorizar_lote(textos_hijos)

        # Etapa 4: inserción en Supabase
        trabajos_repo.actualizar_progreso(job_id, "Insertando en base de datos...")
        insersor.insertar_bloques(bloques, embeddings, documento_id)

        # Todo OK: marcar documento como indexado y job como completado
        docs_repo.actualizar_estado(documento_id, "indexado")
        trabajos_repo.completar(job_id)

    except Exception as e:
        # Rollback: borrar el documento (cascada limpia cualquier chunk
        # que se haya alcanzado a insertar antes del fallo)
        trabajos_repo.marcar_error(job_id, str(e)) 
        docs_repo.eliminar_documento(documento_id)  # ← Luego, cascade limpia chunks padres e hijos


def pipeline_actualizacion(documento_id: str, job_id: str, nombre_archivo: str,
                           texto: str, nuevo_hash: str):
    """
    Pipeline completo para actualizar un documento existente.
    Corre en background tras PUT /documentos/{id}.

    El swap es atómico: los chunks viejos se borran SOLO si el pipeline
    completo tuvo éxito. Si falla antes del swap, los datos viejos
    permanecen intactos y el documento sigue disponible para el chatbot.
    """
    docs_repo = DocumentosRepo()
    trabajos_repo = TrabajosRepo()
    insersor = InsersorSupabase()

    try:
        # Etapa 1: segmentación temática (sobre el nuevo texto)
        trabajos_repo.actualizar_progreso(job_id, "Segmentando documento con Gemini...")
        bloques_texto = _get_segmentador().segmentar(texto)
        total_bloques = len(bloques_texto)

        # Etapa 2: chunking
        trabajos_repo.actualizar_progreso(job_id, f"Generando chunks ({total_bloques} bloques temáticos)...")
        bloques = _get_chunker().generar_chunks_desde_bloques(bloques_texto, nombre_archivo)

        textos_hijos = [
            hijo["texto_embedding"]
            for bloque in bloques
            for hijo in bloque["hijos"]
        ]
        total_hijos = len(textos_hijos)

        # Etapa 3: embeddings
        trabajos_repo.actualizar_progreso(job_id, f"Vectorizando {total_hijos} fragmentos...")
        embeddings = _get_embedder().vectorizar_lote(textos_hijos)

        # Etapa 4: swap atómico
        # Solo aquí se tocan los datos viejos, una vez que el pipeline
        # completo tuvo éxito. Primero borramos los chunks viejos (cascada
        # a hijos), luego insertamos los nuevos con el mismo documento_id.
        trabajos_repo.actualizar_progreso(job_id, "Reemplazando datos anteriores...")
        docs_repo.eliminar_chunks(documento_id)
        insersor.insertar_bloques(bloques, embeddings, documento_id)

        # Actualizar hash y versión del documento
        docs_repo.actualizar_tras_reproceso(documento_id, nuevo_hash)
        trabajos_repo.completar(job_id)

    except Exception as e:
        # No se borra el documento — los datos viejos siguen intactos
        docs_repo.actualizar_estado(documento_id, "indexado")
        trabajos_repo.marcar_error(job_id, str(e))