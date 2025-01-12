from imports import *

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Upstash Redis Configuration
URL = os.getenv("URL")
TOKEN = os.getenv("TOKEN")
history = UpstashRedisChatMessageHistory(
    url=URL,
    token=TOKEN,
    session_id="chat1",
    ttl=86400  # Unique session ID for persistent memory
)

# Memory setup for permanent storage (no TTL)
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    chat_memory=history,
)

# Function to load and process the PDF
def load_and_process_pdf(pdf_path):
    # Load PDF using Langchain's PyPDFLoader
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    # Extract text from the documents
    pdf_text = "\n".join([doc.page_content for doc in documents])

    # Split text by bullet points (assuming common bullet symbols like '-', '*', '•')
    bullet_point_pattern = r"(\n?[-•*]\s)"
    sections = re.split(bullet_point_pattern, pdf_text)

    # Filter empty sections and strip spaces
    bullet_sections = [section.strip() for section in sections if section.strip()]

    return bullet_sections

# Function to create a vector store (FAISS index) from the PDF content
def create_vector_store_from_pdf(pdf_path):
    # Load and process the PDF, splitting it by bullet points
    sections = load_and_process_pdf(pdf_path)

    # Create embeddings for the split sections
    embeddings = OpenAIEmbeddings()

    # Store sections in a FAISS index
    index = FAISS.from_texts(sections, embeddings)

    return index

# Initialize the bot and chain
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

# Function to process chat and get response
def process_chat(chain, retriever, question, chat_history):
    # Get response from the chain
    response = chain.invoke({
        "input": question,
        "chat_history": chat_history,
        "context": retriever.get_relevant_documents(question)
    })
    
    # Check if response is a string or dictionary
    if isinstance(response, dict):
        return response.get('output', '')
    else:
        return response  # Return the string directly


# Web App Routes
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
    # Generate a unique session ID
    new_session_id = str(uuid.uuid4())
    
    # Initialize a new session in Redis
    new_history = UpstashRedisChatMessageHistory(
        url=URL,
        token=TOKEN,
        session_id=new_session_id,
        ttl=86400  # Optional: Set TTL for new chat session
    )
    
    memory.chat_memory = new_history
    return jsonify({"session_id": new_session_id, "message": "New chat session created!"})

@app.route('/get_chats', methods=['GET'])
def get_chats():
    keys = history.redis_client.keys('*')  # Use Upstash Redis client
    chat_keys = [key for key in keys]  # Decode keys to string
    return jsonify({"chats": chat_keys})

@app.route('/get_chat_history/<session_id>', methods=['GET'])
async def get_chat_history(session_id):
    try:
        # Retrieve messages for the specific session from Redis
        specific_history = UpstashRedisChatMessageHistory(
            url=URL,
            token=TOKEN,
            session_id=session_id
        )
        messages = specific_history.redis_client.lrange(session_id, start=0, stop=-1)
        
        # Return the formatted messages as a JSON response
        return jsonify({"messages": messages})
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return jsonify({"error": "Failed to fetch chat history"}), 500

# Initialize the PDF processing and FAISS index
pdf_path = "C:\\LANGBOT\\uploads\\part2.pdf"  # Replace with the path to your PDF
vector_store = create_vector_store_from_pdf(pdf_path)
chain, retriever = create_chain(vector_store)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
