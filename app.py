from fastapi import Depends, FastAPI
from pydantic import BaseModel
from gemini_chat import GeminiChat
from database.retriever import Retriever
from fastapi.middleware.cors import CORSMiddleware
from auth import autenticar_admin, obtener_admin_actual
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi import UploadFile, File, BackgroundTasks, HTTPException
from database.documentos_repo import DocumentosRepo
from database.trabajos_repo import TrabajosRepo
from pipeline import pipeline_alta, pipeline_actualizacion
from auth import autenticar_admin, obtener_admin_actual, cambiar_password

app = FastAPI(
    title="Chatbot Servicio Social UPIICSA",
    description="API para resolver dudas sobre el proceso de servicio social en la UPIICSA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # para desarrollo; restringir en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración del limiter
# Ajustar aquí si se necesita cambiar el límite de intentos de login
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

gemini_chat = GeminiChat()
retriever = Retriever()

# ---------------------------- Modelos ----------------------------
class ConsultaRequest(BaseModel):
    pregunta: str

class ConsultaResponse(BaseModel):
    respuesta: str

class LoginRequest(BaseModel):
    usuario: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DocumentoResponse(BaseModel):
    id_documento: str
    nombre_archivo: str
    fecha_carga: str
    estado: str
    version: int
 
class AltaResponse(BaseModel):
    documento_id: str
    job_id: str
 
class EstadoJobResponse(BaseModel):
    job_id: str
    documento_id: str
    tipo: str
    estado: str
    progreso: str | None = None
    mensaje_error: str | None = None

class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str
    password_nueva_confirmacion: str

# ---------------------------- Endpoints ----------------------------
@app.post("/consulta", response_model=ConsultaResponse)
def consultar(request: ConsultaRequest):
    contexto = retriever.obtener_contexto_concatenado(request.pregunta)
    texto_generado = gemini_chat.consultar_llm(request.pregunta, contexto)
    return ConsultaResponse(respuesta=texto_generado)

@app.get("/ping")
def ping():
    try:
        retriever.supabase.table("chunks_padres").select("id_chunk_padre").limit(1).execute()
        return {"status": "ok", "db": "alive"}
    except Exception as e:
        return {"status": "ok", "db": "error", "detail": str(e)}

@app.post("/login", response_model=LoginResponse)
@limiter.limit("5/5minutes")
def login(request: Request, datos: LoginRequest):
    token = autenticar_admin(datos.usuario, datos.password)
    return LoginResponse(access_token=token)

# Endpoint de prueba para verificar que la protección funciona - quitar en produccion
@app.get("/admin/verificar")
def verificar_sesion(admin: str = Depends(obtener_admin_actual)):
    return {"usuario": admin, "mensaje": "Sesión válida"}

@app.get("/documentos", response_model=list[DocumentoResponse])
def listar_documentos(admin: str = Depends(obtener_admin_actual)):
    """Lista todos los documentos indexados, ordenados por fecha de carga descendente."""
    repo = DocumentosRepo()
    return repo.listar()
 
@app.post("/documentos", response_model=AltaResponse, status_code=202)
async def subir_documento(background_tasks: BackgroundTasks, archivo: UploadFile = File(...), admin: str = Depends(obtener_admin_actual)):
    """
    Sube un PDF nuevo. Extrae el texto, verifica duplicados por hash,
    registra el documento y dispara el pipeline en background.
    Responde inmediatamente con documento_id y job_id para polling.
    """
    if not archivo.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")
 
    contenido = await archivo.read()
 
    # Extraer texto en memoria (no se guarda el PDF en disco ni en BD)
    from indexador.extractor_pdf import Extractor
    import io
    extractor = Extractor()
    texto = extractor.extraer_de_buffer(contenido)
 
    # Verificar duplicado por hash del texto extraído
    docs_repo = DocumentosRepo()
    hash_contenido = DocumentosRepo.calcular_hash(texto)
 
    if docs_repo.existe_hash(hash_contenido):
        raise HTTPException(
            status_code=409,
            detail="Ya existe un documento con este contenido indexado."
        )
 
    # Crear registros en BD (síncrono, antes de responder)
    documento_id = docs_repo.crear_documento(archivo.filename, hash_contenido)
    trabajos_repo = TrabajosRepo()
    job_id = trabajos_repo.crear_trabajo(documento_id, "alta")
 
    # Disparar pipeline en background (asíncrono, después de responder)
    background_tasks.add_task(
        pipeline_alta,
        documento_id, job_id, archivo.filename, texto
    )
 
    return AltaResponse(documento_id=documento_id, job_id=job_id)

@app.put("/documentos/{documento_id}", response_model=AltaResponse, status_code=202)
async def actualizar_documento(documento_id: str, background_tasks: BackgroundTasks, archivo: UploadFile = File(...), admin: str = Depends(obtener_admin_actual)):
    """
    Actualiza un documento existente. Corre el pipeline completo sobre
    el nuevo PDF y solo reemplaza los chunks viejos si todo tiene éxito.
    Los datos anteriores permanecen intactos hasta el swap final.
    """
    if not archivo.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")
 
    docs_repo = DocumentosRepo()
    doc = docs_repo.obtener_por_id(documento_id)
 
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
 
    contenido = await archivo.read()
 
    from indexador.extractor_pdf import Extractor
    extractor = Extractor()
    texto = extractor.extraer_de_buffer(contenido)
 
    nuevo_hash = DocumentosRepo.calcular_hash(texto)
 
    # Si el contenido es idéntico, no hay nada que hacer
    if nuevo_hash == doc["hash_contenido"]:
        raise HTTPException(
            status_code=304,
            detail="El contenido del PDF es idéntico al actualmente indexado."
        )
 
    # Marcar documento como pendiente durante el reproceso
    docs_repo.actualizar_estado(documento_id, "pendiente")
 
    trabajos_repo = TrabajosRepo()
    job_id = trabajos_repo.crear_trabajo(documento_id, "actualizacion")
 
    background_tasks.add_task(
        pipeline_actualizacion,
        documento_id, job_id, archivo.filename, texto, nuevo_hash
    )
 
    return AltaResponse(documento_id=documento_id, job_id=job_id)
 
 
@app.delete("/documentos/{documento_id}", status_code=204)
def eliminar_documento(documento_id: str, admin: str = Depends(obtener_admin_actual)):
    """
    Elimina un documento y toda su información indexada.
    La cascada en BD limpia chunks_padres y chunks_hijos automáticamente.
    """
    docs_repo = DocumentosRepo()
    doc = docs_repo.obtener_por_id(documento_id)
 
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
 
    docs_repo.eliminar_documento(documento_id)
 
 
@app.get("/indexar/estado/{job_id}", response_model=EstadoJobResponse)
def estado_job(job_id: str, admin: str = Depends(obtener_admin_actual)):
    """
    Consulta el estado de un trabajo de indexación.
    Lee de la BD, no de memoria — funciona aunque el servidor se reinicie.
    """
    trabajos_repo = TrabajosRepo()
    job = trabajos_repo.obtener(job_id)
 
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
 
    return EstadoJobResponse(
        job_id=job["id_job"],
        documento_id=job["documento_id"],
        tipo=job["tipo"],
        estado=job["estado"],
        progreso=job.get("progreso"),
        mensaje_error=job.get("mensaje_error")
    )

@app.put("/admin/password", status_code=200)
def actualizar_password(request: CambiarPasswordRequest,admin: str = Depends(obtener_admin_actual)):
    """
    Cambia la contraseña del administrador autenticado.
    Requiere la contraseña actual para confirmar identidad,
    más la nueva contraseña en dos campos para evitar errores de tipeo.
    """
    if request.password_nueva != request.password_nueva_confirmacion:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña y su confirmación no coinciden"
        )

    if len(request.password_nueva) < 8:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe tener al menos 8 caracteres"
        )

    cambiar_password(admin, request.password_actual, request.password_nueva)
    return {"mensaje": "Contraseña actualizada correctamente"}