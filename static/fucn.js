const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const chatHistory = document.getElementById("chat-history");
const sidebar = document.getElementById("sidebar");
const oldChatsList = document.getElementById("old-chats-list");

// Function to open the sidebar
function openSidebar() {
    sidebar.style.width = "250px";
    fetchOldChats();
}

// Function to close the sidebar
function closeSidebar() {
    sidebar.style.width = "0";
}

// Function to send a message and get a response
chatForm.addEventListener("submit", async function(event) {
    event.preventDefault();

    const message = userInput.value.trim();
    if (!message) return;

    userInput.value = '';

    // Display user's message in the chat history
    const userMessage = document.createElement('div');
    userMessage.classList.add("message", "user");
    userMessage.textContent = `You: ${message}`;
    chatHistory.appendChild(userMessage);

    // Send the message to the backend
    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `user_input=${encodeURIComponent(message)}`
        });

        const data = await response.json();
        const formattedResponse = formatResponse(data.response);

        // Display the bot's response
        const botMessage = document.createElement('div');
        botMessage.classList.add("message", "bot");
        botMessage.innerHTML = `Assistant: ${formattedResponse}`;
        chatHistory.appendChild(botMessage);

        // Scroll to the latest message
        chatHistory.scrollTop = chatHistory.scrollHeight;
    } catch (error) {
        console.error("Error communicating with the server:", error);
    }
});

function createNewChat() {
    fetch('/new_chat', {
        method: 'POST',
    })
        .then(response => response.json())
        .then(data => {
            // Reset the chat history and memory for the new chat session
            chatHistory.innerHTML = `<h3>New Chat (${data.session_id})</h3>`;
            memory.chat_memory = [];
            userInput.value = '';
            alert(data.message);
            
            // Optionally, refresh the old chats list in the sidebar
            fetchOldChats();
        })
        
}


// Function to load old chats from the server
async function fetchOldChats() {
    try {
        const response = await fetch('/get_chats');
        const data = await response.json();

        oldChatsList.innerHTML = ''; // Clear the list first

        if (data.chats && Array.isArray(data.chats)) {
            data.chats.forEach((chatId) => {
                const chatLink = document.createElement('a');
                chatLink.href = "#"; // Prevent direct navigation
                chatLink.textContent = `Chat ${chatId}`;
                chatLink.onclick = () => loadChatContent(chatId); // Fetch content dynamically
                oldChatsList.appendChild(chatLink);
            });
        } else {
            oldChatsList.textContent = "No old chats available.";
        }
    } catch (error) {
        console.error("Error fetching old chats:", error);
    }
}


// Function to load the content of a selected chat
function loadChatContent(sessionId) {
    // Prevent direct navigation to the link
    event.preventDefault();

    // Clear the current chat history area
    chatHistory.innerHTML = '<p>Loading chat...</p>';

    // Fetch the chat history from the server based on sessionId
    fetch(`/get_chat_history/${sessionId}`)
        .then(response => response.json())
        .then(data => {
            chatHistory.innerHTML = ''; // Clear the "Loading" message

            if (data.messages && data.messages.length > 0) {
                // Loop through the messages and display them in the chat history
                data.messages.forEach(msg => {
                    msg = JSON.parse(msg); // Parse each message JSON
                    const messageDiv = document.createElement('div');
                    messageDiv.classList.add(
                        "message",
                        msg.type === "human" ? "user" : "bot"
                    );
                    messageDiv.textContent = `${msg.type}: ${msg.data.content}`;
                    chatHistory.appendChild(messageDiv);
                });
            } else {
                // If no messages, display a default message
                chatHistory.innerHTML = "<p>No chat history available.</p>";
            }

            // Scroll to the latest message
            chatHistory.scrollTop = chatHistory.scrollHeight;
        })
        .catch(error => {
            console.error("Error loading chat history:", error);
            alert("Failed to load chat history. Please try again.");
        });
}


// Function to format responses with code block
function formatResponse(response) {
    if (response.startsWith("```") && response.endsWith("```")) {
        return `<pre><code>${response.slice(3, -3).trim()}</code></pre>`;
    }
    return response;
}

// Load old chats when the page is loaded
window.onload = () => {
    fetchOldChats();
};