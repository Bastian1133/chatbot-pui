from dotenv import load_dotenv
import os
import json
# Configuracion LLM - Gemini
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

class GeminiChat:
    def __init__(self):
        load_dotenv("keys.env") # Carga las variables de entorno desde el archivo keys.env
        
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Obtiene la clave de API de Gemini desde las variables de entorno
        
        if not GEMINI_API_KEY:
            raise ValueError("Falta la API key de Gemini en el archivo keys.env")

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview",
            temperature=0.2, # Ajusta la temperatura para controlar la creatividad de las respuestas
            max_tokens=2048 # Ajusta el número máximo de tokens en la respuesta
        )
        self.system_prompt = """
        Eres un asistente virtual especializado en la PUI (Plataforma Única de 
        Identidad) y el SIGED (Sistema de Información y Gestión Educativa), 
        de la Dirección General de Acreditación, Incorporación y Revalidación 
        (DGAIR) de la SEP.
        Sé conciso y directo.
        Responde usando Markdown cuando ayude a la claridad: usa listas con viñetas 
        para enumerar requisitos o pasos, y negritas para resaltar términos clave 
        (como nombres de campos, códigos de error, plazos o correos de contacto).
 
        Si el usuario pregunta sobre tu propósito, qué eres o en qué puedes ayudar,
        explica que eres un asistente especializado en resolver dudas sobre la 
        carga de información en el SIGED y el proceso de la PUI: llenado del 
        layout de Control Escolar, conversión de archivos, errores de validación,
        catálogos (Institución-Carrera-RVOE), claves (CCT, RVOE), y canales de 
        contacto. Esto lo puedes responder sin necesidad de texto de referencia.
 
        Para cualquier otra pregunta:
        Si no sabes algo con absoluta certeza, dilo claramente en lugar de inventar, 
        es muy importante que la información que brindes sea real.
        No incluyas información que no esté en el texto de referencia, que viene 
        dado en cada consulta siguiendo TEXTO DE REFERENCIA: 'contexto'.
        Si tu respuesta no está basada en el texto de referencia, no la incluyas.
        Si el texto de referencia no tiene la información necesaria para responder,
        di que no tienes suficiente información para responder e invita al usuario 
        a reformular su pregunta, proporcionar más detalles, o consultar el canal 
        de contacto correspondiente (comunicacionpui@nube.sep.gob.mx), es obligatorio
        que solicites amablemente al usuario que mande la pregunta que no pudo ser 
        respondida a dicho correo.
        No menciones el texto de referencia en ninguna de tus respuestas, ni digas que la información proviene de él.
        """

    def consultar_llm(self, consulta, mejor_pasaje):
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", """
            
            PREGUNTA: '{consulta}'
            TEXTO DE REFERENCIA: '{pasaje_relevante}'

            RESPUESTA:
            """
            ),
        ])
        # Imprimir el prompt ya formateado, antes de enviarlo - solo para depuración
        # prompt_formateado = prompt.format(consulta=consulta, pasaje_relevante=mejor_pasaje)
        # print("=== Prompt generado ===")
        # print(prompt_formateado)
        # print("========================\n")  

        chain = prompt | self.llm | StrOutputParser()
        # for chunk in chain.stream(mensajes):
        #     print(chunk, end="", flush=True)
        resultado = chain.invoke({
            "consulta": consulta,
            "pasaje_relevante": mejor_pasaje,
        })
        return resultado

