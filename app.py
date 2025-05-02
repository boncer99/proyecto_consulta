#http://127.0.0.1:5000/movie?pelicula=terminator
from dotenv import load_dotenv
import os

import sys
from flask import Flask, jsonify, request

#from langchain.chat_models import ChatOpenAI
#from langchain_community.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI

from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool

from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnableSequence
from flask import Flask, request, render_template, jsonify

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

load_dotenv()
openai_api_key = os.environ.get("OPENAI_API_KEY")
uribd = os.getenv("DB_ACCESS")
#openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

def obtener_genero(pelicula_name):
    prompt = ChatPromptTemplate.from_template("Indica en una palabra de qué género es la película: {pelicula}")
    #llm = ChatOpenAI()
    llm = ChatOpenAI(openai_api_key=openai_api_key)
    parser = StrOutputParser()
    pipeline = RunnableSequence(prompt | llm | parser)
    return pipeline.invoke({"pelicula": pelicula_name})

@app.route('/', methods=['GET', 'POST'])
def main():
    resultado =""
    if request.method == 'POST':
        pelicula_name = request.form.get('pelicula')
        resultado = obtener_genero(pelicula_name)
    return render_template('index.html', resultado=resultado)


@app.route('/movie', methods=['GET'])
def get_movie():
    pelicula_name = request.args.get('pelicula')
    if not pelicula_name:
        return jsonify({"error": "Debe enviar el parámetro 'pelicula'"}), 400
    resultado = obtener_genero(pelicula_name)
    return jsonify({"genero": resultado})


#Creamos la conexion a la base de datos
db_data = SQLDatabase.from_uri(uribd)
# Herramienta BD
toolkit_bd = SQLDatabaseToolkit(db=db_data,llm=ChatOpenAI(openai_api_key=openai_api_key,temperature=0))
tools_bd = toolkit_bd.get_tools()


def seleccionar_tabla_v2(question: str) -> str:
    """
    Selecciona la tabla correcta basada en la pregunta utilizando la LLM para inferir el nombre de la tabla,
    y luego verifica si el nombre de la tabla existe en las tablas disponibles.
    """
    # Obtiene las tablas disponibles desde la base de datos
    tablas_disponibles = db_data.get_table_names()  # Listado dinámico de tablas

    # Crea un mensaje que pasa la lista de tablas disponibles al modelo de lenguaje
    tablas_str = ", ".join(tablas_disponibles)  # Las tablas disponibles como un string

    # Consultamos a la LLM para obtener el nombre de la tabla basado en la pregunta y las tablas disponibles
    prompt = (f"Las siguientes tablas están disponibles en la base de datos: {tablas_str}. "
              f"Segun las tablas indicadas  ¿Devuelve sólo el nombre de la tabla a  la que corresponde esa pregunta: '{question}'?")
    #model = ChatOpenAI(verbose=True)
    model = ChatOpenAI(openai_api_key=openai_api_key,verbose=True)
    # Suponiendo que 'model' es el objeto que invoca el modelo de lenguaje
    #nombre_tabla_sugerido = model(prompt).strip().lower()  # Respuesta procesada a minúsculas
    respuesta = model.invoke([HumanMessage(content=prompt)])
    nombre_tabla_sugerido = respuesta.content.strip().lower()

    # Validamos si la tabla sugerida por el modelo existe en la base de datos
    #if nombre_tabla_sugerido not in tablas_disponibles:
    #    return f"[ERROR] La tabla '{nombre_tabla_sugerido}' no se reconoce. Las tablas disponibles son: {', '.join(tablas_disponibles)}"

    return nombre_tabla_sugerido

# Función para seleccionar la tabla correcta basada en la pregunta
def seleccionar_tabla(question: str) -> str:
    # Define las tablas disponibles
    tablas_disponibles = ['temperatura_registros', 'humedad_registros', 'calidad_aire_registros', 'sensores', 'historial_dispositivos']

    # Aquí puedes agregar lógica de selección, por ejemplo, buscar palabras clave en la pregunta
    if "temperatura" in question.lower():
        return "temperatura_registros"
    elif "humedad" in question.lower():
        return "humedad_registros"
    elif "calidad de aire" in question.lower():
        return "calidad_aire_registros"
    elif "sensor" in question.lower():
        return "sensores"
    elif "historial" in question.lower():
        return "historial_dispositivos"
    else:
        # Si no se encuentra una coincidencia clara, puede retornar una tabla predeterminada o lanzar un error
        return "temperatura_registros"  # Tabla predeterminada

from pydantic import BaseModel, Field
from langchain_core.tools import Tool


db_data = SQLDatabase.from_uri(uribd)
#model = ChatOpenAI(verbose=True)
model = ChatOpenAI(openai_api_key=openai_api_key,verbose=True)
#model = ChatOpenAI(model="gpt-4o-mini", verbose=True)

#@tool(args_schema=GetSchemaInput)
@tool
def get_schema(question: str) -> str:
    "Herramienta para recuperar el esquema de una tabla específica,si la tabla no existe devuelve un mensaje de error controlado"
    # Usa la función 'seleccionar_tabla' para obtener el nombre de la tabla basándose en la pregunta
    tabla_seleccionada = seleccionar_tabla_v2(question)
    # Obtiene las tablas disponibles desde la base de datos
    tablas_disponibles = db_data.get_table_names()
    # Si la tabla seleccionada no existe en la base de datos, devuelve un mensaje de error controlado
    if tabla_seleccionada not in tablas_disponibles:
        return f"[ERROR] La tabla '{tabla_seleccionada}' no se reconoce. Las tablas disponibles son: {', '.join(tablas_disponibles)}"
    # Si la tabla es válida, devuelve el esquema de la tabla seleccionada
    schema = db_data.get_table_info([tabla_seleccionada])
    return schema


promptsql = ChatPromptTemplate.from_template("""
Basandonos en el esquema de tabla siguiente, escribe una consulta SQL que responda a la pregunta del usuario:
    Tabla: {table}

    Esquema: {schema}

    Pregunta: {question}
    Sql Query:
""")

sqlchain = (
    promptsql
    | model.bind(stop=["\nSQLResult:"])
    | StrOutputParser()
)

@tool
def generar_sql(question: str) -> str:
    """Genera una consulta SQL a partir del esquema, la pregunta y  usando la tabla adecuada seleccionada dinámicamente """
    # Selecciona la tabla basándose en la pregunta
    tabla_seleccionada = seleccionar_tabla(question)
    schema = db_data.get_table_info([tabla_seleccionada])  # Solo obtiene el esquema de la tabla seleccionada
    return sqlchain.invoke({"schema": schema, "question": question,"table": tabla_seleccionada})



@tool
def run_query(query) -> str:
    """Herramienta que ejecuta una consulta SQL en la base de datos"""
    resultado = db_data.run(query)
    if not resultado or resultado == [(None,)]:
        return "[SIN RESULTADOS] No se encontraron registros que coincidan con la consulta."
    return resultado
#def run_query(query) -> str:
#  """Herramienta que ejecuta una consulta SQL en la base de datos"""
#  return db_data.run(query)


promptsqlquery = ChatPromptTemplate.from_template(
    """
    Basandonos en el esquema de tabla inferior, pregunta, SQL Query y Respuesta, escribe una respuesta en lenguaje natural:
    Tabla: {table}

    Esquema: {schema}

    Pregunta: {question}
    Sql Query: {sql_query}
    SQL Respuesta: {response}

    """)

sqlnatural_chain = (
     promptsqlquery
    | model
    | StrOutputParser()
)

@tool(return_direct=True)
def generar_respuesta(question: str, sql_query: str, response: str) -> str:
    """Genera una respuesta en lenguaje natural tomando el esquema, la consulta, la query,la respuesta de la ejecucion de la query y la tabla seleccionada"""
    tabla_seleccionada = seleccionar_tabla(question)
    schema = db_data.get_table_info([tabla_seleccionada])
    return sqlnatural_chain.invoke({"schema": schema, "question": question, "sql_query":sql_query, "response":response, "table": tabla_seleccionada  })


####################Agente SQL#############################################
#model = ChatOpenAI(model="gpt-4o-mini", verbose=True)
#model = ChatOpenAI(verbose=True)
model = ChatOpenAI(openai_api_key=openai_api_key,verbose=True)

memory = MemorySaver()
#construccion del prompt
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """ Eres un asistente de base de datos, utiliza tus herramientas para resolver las preguntas de los usuarios
        """),

     ("human", "{messages}"),

     ]
)

#toolkit = [get_schema,generar_sql,run_query,generar_respuesta]
toolkit = [get_schema,generar_sql,run_query,generar_respuesta]
agent2 = create_react_agent(model, toolkit, checkpointer=memory, prompt=prompt)


import uuid
config = {"configurable": {"thread_id": str(uuid.uuid4())}}

def ejecutar_consulta(pregunta: str) -> str:
    # Generar un ID de hilo dinámico
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # Inicializar la respuesta como string vacío
    respuesta = ""

    # Ejecutar la consulta con el agente en modo streaming
    for step in agent2.stream(
        {"messages": [HumanMessage(content=pregunta)]},
        config,
        stream_mode="values",
    ):
        # Obtener el contenido del último mensaje generado
        mensaje = step["messages"][-1].content

        # Acumular en la respuesta
        respuesta = mensaje
    return respuesta

#resultado = ejecutar_consulta("¿Indica todas las personas que  apagaron las luces en la cocina segun el historial?")
#print("Respuesta del agente:", resultado)


@app.route('/info', methods=['GET', 'POST'])
def consulta():
    resultado_solicitud =""
    if request.method == 'POST':
        texto_consulta = request.form.get('solicitud')
        resultado_solicitud = ejecutar_consulta(texto_consulta)
    return render_template('info.html', resultado_solicitud=resultado_solicitud)

#necesario si se ejecuta de manera local
#if __name__ == "__main__":
#    app.run(debug=True)
