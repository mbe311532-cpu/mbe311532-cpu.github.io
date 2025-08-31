# Groq Chatbot

A Python-based chatbot using the Groq API with real-time information and chat history persistence.

## Features

- Real-time date and time information
- Chat history persistence in JSON format
- Streaming responses from Groq API
- Configurable system prompts
- Error handling and graceful exits

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Configure your .env file:**
   - Get your Groq API key from [Groq Console](https://console.groq.com/)
   - Update the `.env` file with your API key and preferences:
     ```
     GroqAPIKey=your_actual_api_key_here
     Username=YourName
     Assistantname=YourAssistantName
     ```

## Usage

Run the chatbot:
```bash
python chatbot.py
```

- Type your questions and press Enter
- Type `quit`, `exit`, or `bye` to stop the chatbot
- Press `Ctrl+C` to interrupt and exit

## File Structure

```
├── chatbot.py          # Main chatbot script
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .env               # Your environment variables (create this)
└── Data/
    └── ChatLog.json   # Chat history (created automatically)
```

## Dependencies

- `groq`: Groq API client
- `python-dotenv`: Environment variable management
- `datetime`: Built-in Python module for time handling
- `json`: Built-in Python module for JSON operations

## Notes

- The chatbot uses the `llama3-70b-8192` model by default
- Chat history is automatically saved to `Data/ChatLog.json`
- The system is configured to respond only in English
- Real-time information is included in each request