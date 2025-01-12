from imports import *

load_dotenv()
app = Flask(__name__)
URL = os.getenv("URL")
TOKEN = os.getenv("TOKEN")
history = UpstashRedisChatMessageHistory(
    url=URL,
    token=TOKEN,
    session_id="chat1",
    ttl=86400 
)
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    chat_memory=history,
)
uploaded_pdfs = []
def load_and_process_pdf(pdf_path):
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    pdf_text = "\n".join([doc.page_content for doc in documents])
    bullet_point_pattern = r"(\n?[-•*]\s)"
    sections = re.split(bullet_point_pattern, pdf_text)
    bullet_sections = [section.strip() for section in sections if section.strip()]
    return bullet_sections
def create_vector_store_from_pdfs(pdf_paths):
    sections = []
    for pdf_path in pdf_paths:
        sections.extend(load_and_process_pdf(pdf_path))
    embeddings = OpenAIEmbeddings()
    index = FAISS.from_texts(sections, embeddings)
    return index
def create_chain(vectorStore):
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.4)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the user's questions based on the context: {context}"),
        ("human", "{input}")
    ])
    chain = create_stuff_documents_chain(
        llm=model,
        prompt=prompt
    )
    retriever = vectorStore.as_retriever(search_kwargs={"k": 3})
    return chain, retriever
def process_chat(chain, retriever, question, chat_history):
    response = chain.invoke({
        "input": question,
        "chat_history": chat_history,
        "context": retriever.get_relevant_documents(question)
    })
    if isinstance(response, dict):
        return response.get('output', '')
    else:
        return response

# Routes
#_______________________________________________________________________________

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_input = request.form['user_input']
    response = process_chat(chain, retriever, user_input, memory.chat_memory.messages)
    memory.chat_memory.add_message(HumanMessage(content=user_input))
    memory.chat_memory.add_message(AIMessage(content=response))
    return jsonify({"response": response})

@app.route('/new_chat', methods=['POST'])
def new_chat():
    new_session_id = str(uuid.uuid4())
    new_history = UpstashRedisChatMessageHistory(
        url=URL,
        token=TOKEN,
        session_id=new_session_id,
        ttl=86400
    )
    memory.chat_memory = new_history
    return jsonify({"session_id": new_session_id, "message": "New chat session created!"})

@app.route('/get_chats', methods=['GET'])
def get_chats():
    keys = history.redis_client.keys('*') 
    chat_keys = [key for key in keys] 
    return jsonify({"chats": chat_keys})

@app.route('/get_chat_history/<session_id>', methods=['GET'])
async def get_chat_history(session_id):
    try:
        specific_history = UpstashRedisChatMessageHistory(
            url=URL,
            token=TOKEN,
            session_id=session_id
        )
        messages = specific_history.redis_client.lrange(session_id, start=0, stop=-1)
        return jsonify({"messages": messages})
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return jsonify({"error": "Failed to fetch chat history"}), 500


@app.route('/pdf')
def pdf():
    return render_template('pdf.html')
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and file.filename.endswith('.pdf'):
        upload_path = os.path.join("static/pdfs", file.filename)
        file.save(upload_path)
        uploaded_pdfs.append(upload_path)
        global vector_store, chain, retriever
        vector_store = create_vector_store_from_pdfs(uploaded_pdfs)
        chain, retriever = create_chain(vector_store)
        return jsonify({"message": f"PDF '{file.filename}' uploaded and processed successfully!"})
    return jsonify({"error": "Invalid file type"}), 400


initial_pdfs = [
    "static\\pdfs\\part1.pdf",
    "static\\pdfs\\part2.pdf",
    "static\\pdfs\\part3.pdf",
    "static\\pdfs\\part4.pdf",
    "static\\pdfs\\part5.pdf",
    "static\\pdfs\\part6.pdf",
    "static\\pdfs\\part7.pdf",
    "static\\pdfs\\part8.pdf"
]
uploaded_pdfs.extend(initial_pdfs)
vector_store = create_vector_store_from_pdfs(uploaded_pdfs)
chain, retriever = create_chain(vector_store)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
