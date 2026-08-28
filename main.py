# from gemini_chat import GeminiChat
# from documentos import Documentos
# from database.retriever import Retriever

# # Se inicializa la clase GeminiChat
# GeminiChat = GeminiChat()
# Retriever = Retriever()

# print("¿En qué puedo ayudarte?")

# while True:
#     consulta = input("> ")
#     print("")
    
#     if consulta == "salir":
#         print("¡Hasta luego!")
#         break
#     mejor_pasaje = Retriever.obtener_contexto_concatenado(consulta)
#     GeminiChat.consultar_llm(consulta, mejor_pasaje)
#     print("")
