from fastapi import Depends, FastAPI
from pydantic import BaseModel
from gemini_chat import GeminiChat
from database.retriever import Retriever
from fastapi.middleware.cors import CORSMiddleware
from auth import autenticar_admin, obtener_admin_actual

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

@app.post("/consulta", response_model=ConsultaResponse)
def consultar(request: ConsultaRequest):
    contexto = retriever.obtener_contexto_concatenado(request.pregunta)
    texto_generado = gemini_chat.consultar_llm(request.pregunta, contexto)
    return ConsultaResponse(respuesta=texto_generado)

@app.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    token = autenticar_admin(request.usuario, request.password)
    return LoginResponse(access_token=token)

# Endpoint de prueba para verificar que la protección funciona
@app.get("/admin/verificar")
def verificar_sesion(admin: str = Depends(obtener_admin_actual)):
    return {"usuario": admin, "mensaje": "Sesión válida"}