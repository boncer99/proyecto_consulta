# 🎯 **Objetivo General**

**Diseñar y construir un agente inteligente especializado**, capaz de:

- 🛠️ **Utilizar múltiples herramientas personalizadas** (y opcionalmente herramientas de terceros)  
- 🤖 **Ejecutar tareas de forma autónoma y eficiente**
- 💻 Ser **funcional desde un entorno programático** (por ejemplo, en Google Colab o scripts locales)
- 🌐 **Incluir una interfaz web** (opcional) desplegada en **[Vercel](https://vercel.com/)** como valor agregado


## **1. Diagrama de arquitectura.**
El sistema permite a los usuarios interactuar mediante lenguaje natural para realizar consultas de información en una base de datos. Utiliza herramientas personalizadas (tools) para identificar la tabla adecuada, generar y ejecutar una consulta SQL,  y convertir el resultado en una respuesta. Todo el proceso se realiza mediante un agente basado en LangChain y la API de OpenAI. 


<p align="center">
  <img src="https://github.com/user-attachments/assets/e67128a2-0065-4e84-aea2-357f9fbc8acc" width="600"/>
</p>

## **2	Descripción de herramientas y funciones.**
### **3.1	get_schema(question: str) -> str**
El propósito es recuperar el esquema (estructura) de una tabla específica de la base de datos, a partir de una pregunta. Para hacerlo se llama a la función seleccionar_tabla_v2() para inferir el nombre de la tabla más adecuada según la pregunta. Posteriormente verifica si la tabla existe en la base de datos utilizando db_data.get_table_names(). 
En caso la tabla existe, devuelve su esquema mediante db_data.get_table_info([tabla]), pero si no existe, retorna un mensaje de error indicando las tablas válidas.
### **3.2	seleccionar_tabla_v2(question: str) -> str**
Se utiliza para inferir el nombre de la tabla más relevante en función de una pregunta del usuario. Para ello realiza la consulta sobre todas las tablas disponibles en la base de datos y genera un prompt para el modelo de lenguaje con la pregunta del usuario y las tablas disponibles.
El modelo genera como respuesta el nombre de la tabla sugerida y se valida que dicha tabla exista en la base de datos antes de retornarla.
### **3.3	generar_sql(question: str) -> str**
Se encarga de generar una consulta SQL válida basada en la pregunta del usuario y el esquema de la tabla relevante.  Para ello se vuelve a utilizar la función seleccionar_tabla() para y se obtiene el esquema mediante db_data.get_table_info(). 
Posteriormente se usa una cadena (sqlchain) que incluye una plantilla de prompt que genera la consulta SQL con el modelo de lenguaje, devolviendo la consulta generada como una cadena de texto.
### **3.4	run_query(query: str) -> str**
Se utiliza para ejecutar una consulta SQL directamente en la base de datos y retornar los resultados, mediante el objeto db_data, como una instancia de SQLDatabase. Posteriormente ejecuta query utilizando db_data.run(query) que devuelve los resultados obtenidos, los cuales pueden estar vacíos si no hay registros coincidentes.
### **3.5	generar_respuesta(question: str, sql_query: str, response: str) -> str**
Se encarga de generar una respuesta en lenguaje natural basada en la pregunta original, la consulta SQL generada y los resultados de la base de datos.
Se identifica la tabla relacionada con la pregunta mediante seleccionar_tabla() y se utiliza una plantilla (sqlnatural_chain) para que el modelo de lenguaje genere una explicación natural combinando la pregunta, la SQL generada y la respuesta obtenida, devolviendo una respuesta comprensible para el usuario final.


## **3.	Flujo de funcionamiento  (Tool Invocation)**
El agente sigue el modelo ReAct (Razonamiento + Acción), por lo que decide qué herramienta debe usar en cada paso. Se seguirá el siguiente flujo de herramientas:

**a) Herramienta 1:**  
- `get_schema(question: str)` para determinar qué tabla usar y recuperar su esquema.  
- Recibe la variable `question` (pregunta del usuario).  
  - Llama a `seleccionar_tabla_v2(question)` → retorna por ejemplo `"temperatura_registros"`.  
  - Consulta a `db_data.get_table_names()` para verificar si la tabla existe.  
  - Si es válida, llama a `db_data.get_table_info([tabla])` y retorna el esquema.  
- Variable de salida: `schema` (estructura de la tabla en SQL).  

**b) Herramienta 2:** `generar_sql(question: str)`. Generar una sentencia SQL válida.  
- Recibe la variable: `question` (misma pregunta original).  
- Llama a `seleccionar_tabla(question)` → determina la tabla.  
  - Recupera el `schema` de esa tabla.  
  - Ingresa `question`, `table` y `schema` en un prompt (`promptsql`) que genera una SQL.  
  - Usa `sqlchain.invoke(...)` para obtener algo como:  
    ```sql
    SELECT MAX(temperatura) FROM temperatura_registros WHERE fecha >= CURRENT_DATE - INTERVAL '30 days';
    ```  
- Variable de salida: `sql_query`.  

**c) Herramienta 3:** `run_query(query: str)`. Ejecutar la consulta SQL sobre la base de datos.  
- Variable que recibe: `query` (la consulta SQL generada).  
  - Usa `db_data.run(query)` que internamente llama al motor SQL (Postgres).  
  - El resultado puede ser, por ejemplo:  
    ```json
    [{"max": 34.2}]
    ```  
- Variable de salida: `response`.  

**d) Herramienta 4:** `generar_respuesta(question, sql_query, response)`. Transformar la respuesta cruda de SQL en una explicación clara para el usuario.  
- Variable recibida es:  
  - `question`  
  - `sql_query`: la consulta generada.  
  - `response`: el resultado del SQL.  
- Proceso interno:  
  - Llama a `seleccionar_tabla(question)` para identificar la tabla.  
  - Usa `db_data.get_table_info([tabla])` para obtener `schema`.  
  - Inserta `question`, `schema`, `table`, `sql_query` y `response` en un prompt de resumen (`promptsqlquery`).  
  - El modelo genera una frase natural como:  
    > "El valor máximo de temperatura registrado en el último mes fue 34.2°C."

# **4. Instrucciones de ejecución**

### 5.1 Ejecutar el programa en Google Colab

**a) Instala las librerías necesarias al inicio del notebook:**  
- Se crean archivos las claves de openai  
- Generar una API Key de OpenAI  
- Enlace: https://platform.openai.com/account/api-keys  
- Haz clic en “Create new secret key”.  
- Copia la clave generada y úsala como `OPENAI_API_KEY`.  

**b) Generar una API Key de OpenAI**  
- Ir a: https://platform.openai.com/account/api-keys  
- Haz clic en “Create new secret key”.  
- Copia la clave generada y úsala como `OPENAI_API_KEY`.  

**c) Crear una base de datos PostgreSQL en Railway**  
- Entra a: https://railway.app  
- Regístrate e inicia sesión.  
- Crea un nuevo proyecto → selecciona **PostgreSQL Plugin**.  
- Copia la Database URL (formato: `postgresql://usuario:clave@host:puerto/db`).  
- Se usa dentro de un archivo para importarlo.  

**d) Construir y administrar la base con pgAdmin**  
- Descarga e instala pgAdmin desde: https://www.pgadmin.org/download/  
- Abre pgAdmin y crea una nueva conexión:  
  - **Hostname**: copiado desde Railway  
  - **User, Password, Port**: desde Railway también  
- Ingresar el script de creación de tablas y datos.  

**e) Construcción del agente**  
Una vez importadas las llaves de acceso y creación de herramientas se construye el agente para ejecutarlo con preguntas del usuario; el agente elige automáticamente qué herramientas usar según el contexto y devuelve una respuesta precisa.  
La pregunta del usuario, escrita en lenguaje natural, se encapsula en un `HumanMessage` y se envía al agente junto con un identificador de hilo (`thread_id`) que permite rastrear la conversación.  
El agente analiza la pregunta, selecciona las herramientas necesarias. Finalmente, la respuesta generada por el agente se imprime usando `pretty_print()`.
