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

# ---------------------------- Endpoints ----------------------------
@app.post("/consulta", response_model=ConsultaResponse)
def consultar(request: ConsultaRequest):
    contexto = retriever.obtener_contexto_concatenado(request.pregunta)
    texto_generado = gemini_chat.consultar_llm(request.pregunta, contexto)
    return ConsultaResponse(respuesta=texto_generado)

@app.post("/login", response_model=LoginResponse)
@limiter.limit("5/5minutes")
def login(request: Request, datos: LoginRequest):
    token = autenticar_admin(datos.usuario, datos.password)
    return LoginResponse(access_token=token)

# Endpoint de prueba para verificar que la protección funciona
@app.get("/admin/verificar")
def verificar_sesion(admin: str = Depends(obtener_admin_actual)):
    return {"usuario": admin, "mensaje": "Sesión válida"}