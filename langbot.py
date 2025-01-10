from flask import Flask, render_template, request, jsonify
import asyncio
import uuid
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.faiss import FAISS
from langchain.chains import create_retrieval_chain
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains.history_aware_retriever import create_history_aware_retriever

from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain_community.chat_message_histories.upstash_redis import UpstashRedisChatMessageHistory

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

# Initialize the bot
def get_documents_from_web(urls):
    all_docs = []
    for url in urls:
        loader = WebBaseLoader(url)
        docs = loader.load()
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=20
        )
        splitDocs = splitter.split_documents(docs)
        all_docs.extend(splitDocs)
    return all_docs

def create_db(docs):
    embedding = OpenAIEmbeddings()
    vectorStore = FAISS.from_documents(docs, embedding=embedding)
    return vectorStore

def create_chain(vectorStore):
    model = ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        temperature=0.4
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the user's questions based on the context: {context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    chain = create_stuff_documents_chain(
        llm=model,
        prompt=prompt
    )

    retriever = vectorStore.as_retriever(search_kwargs={"k": 3})

    retriever_prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("human", "Given the above conversation, generate a search query to look up in order to get information relevant to the conversation")
    ])

    history_aware_retriever = create_history_aware_retriever(
        llm=model,
        retriever=retriever,
        prompt=retriever_prompt
    )

    retrieval_chain = create_retrieval_chain(
        history_aware_retriever,
        chain
    )

    return retrieval_chain



def process_chat(chain, question, chat_history):
    response = chain.invoke({
        "input": question,
        "chat_history": chat_history
    })
    return response["answer"]

# Initialize documents and chain when the server starts
urls = ['https://docs.crustdata.com/docs/intro' , 'https://docs.crustdata.com/docs/discover/company-data-api' 
          , 'https://docs.crustdata.com/docs/discover/people-data-api' , 'https://docs.crustdata.com/docs/discover/company-search-api-via-filters' , 
          'https://docs.crustdata.com/docs/discover/people-search-api-via-filters' , 'https://docs.crustdata.com/docs/discover/how-to-build-filters'
          , 'https://docs.crustdata.com/docs/dictionary/company' , 'https://docs.crustdata.com/docs/dictionary/people' ,
          'https://docs.crustdata.com/api' , 'https://docs.crustdata.com/api#tag/company-api/GET/screener/company' , 
          'https://docs.crustdata.com/api#tag/company-api/POST/screener/screen/' , 'https://docs.crustdata.com/api#tag/company-api/POST/screener/company/search'
          , 'https://docs.crustdata.com/api#tag/people-api' , 'https://docs.crustdata.com/api#tag/people-api/POST/screener/person/search' , 
          'https://docs.crustdata.com/api#tag/people-api/GET/screener/person/enrich' , 'https://docs.crustdata.com/api#tag/people-api/GET/screener/linkedin_posts'
          
          ]
docs = get_documents_from_web(urls)
vectorStore = create_db(docs)
chain = create_chain(vectorStore)


# Web App Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_input = request.form['user_input']
    response = process_chat(chain, user_input, memory.chat_memory.messages)
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




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)