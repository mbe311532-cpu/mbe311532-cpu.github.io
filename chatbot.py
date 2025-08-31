from groq import Groq  # Importing the Groq library to use its API.
from json import load, dump  # Importing functions to read and write JSON files.
import datetime  # Importing the datetime module for real-time date and time information.
from dotenv import dotenv_values  # Importing dotenv_values to read environment variables from a .env file.
import os  # Importing os for path operations.

# Load environment variables from the .env file.
env_vars = dotenv_values(".env")

# Retrieve specific environment variables for username, assistant name, and API key.
Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
GroqAPIKey = env_vars.get("GroqAPIKey")

# Check if required environment variables are present
if not GroqAPIKey:
    print("Error: GroqAPIKey not found in .env file")
    exit(1)

if not Username:
    print("Warning: Username not found in .env file, using default")
    Username = "User"

if not Assistantname:
    print("Warning: Assistantname not found in .env file, using default")
    Assistantname = "Assistant"

print(f"Groq API Key loaded: {'*' * len(GroqAPIKey) if GroqAPIKey else 'Not found'}")

# Initialize the Groq client using the provided API key.
client = Groq(api_key=GroqAPIKey)

# Create Data directory if it doesn't exist
os.makedirs("Data", exist_ok=True)

# Define a system message that provides context to the AI chatbot about its role and behavior.
System = f"""Hello, I am {Username}, You are a very accurate and advanced AI chatbot named {Assistantname} which also has real-time up-to-date information from the internet.
*** Do not tell time until I ask, do not talk too much, just answer the question.***
*** Reply in only English, even if the question is in Hindi, reply in English.***
*** Do not provide notes in the output, just answer the question and never mention your training data. ***
"""

# Attempt to load the chat log from a JSON file.
try:
    with open("Data/ChatLog.json", "r") as f:
        messages = load(f)  # Load existing messages from the chat log.
except FileNotFoundError:
    # If the file doesn't exist, create an empty JSON file to store chat logs.
    messages = []
    with open("Data/ChatLog.json", "w") as f:
        dump([], f)
except Exception as e:
    print(f"Error loading chat log: {e}")
    messages = []

# Function to get real-time date and time information.
def RealtimeInformation():
    current_date_time = datetime.datetime.now()  # Get the current date and time.
    day = current_date_time.strftime("%A")  # Day of the week.
    date = current_date_time.strftime("%d")  # Day of the month.
    month = current_date_time.strftime("%B")  # Full month name.
    year = current_date_time.strftime("%Y")  # Year.
    hour = current_date_time.strftime("%H")  # Hour in 24-hour format.
    minute = current_date_time.strftime("%M")  # Minute.
    second = current_date_time.strftime("%S")  # Second.

    # Format the information into a string.
    data = f"Please use this real-time information if needed,\n"
    data += f"Day: {day}\nDate: {date}\nMonth: {month}\nYear: {year}\n"
    data += f"Time: {hour} hours :{minute} minutes :{second} seconds.\n"
    return data

# Function to modify the chatbot's response for better formatting.
def AnswerModifier(Answer):
    lines = Answer.split('\n')  # Split the response into lines.
    non_empty_lines = [line for line in lines if line.strip()]  # Remove empty lines.
    modified_answer = '\n'.join(non_empty_lines)  # Join the cleaned lines back together.
    return modified_answer

# Main chatbot function to handle user queries.
def ChatBot(Query):
    """ This function sends the user's query to the chatbot and returns the AI's response. """

    try:
        # Load the existing chat log from the JSON file.
        with open("Data/ChatLog.json", "r") as f:
            messages = load(f)
    except Exception as e:
        print(f"Error loading chat log: {e}")
        messages = []

    # Append the user's query to the messages list.
    messages.append({"role": "user", "content": f"{Query}"})

    try:
        # Make a request to the Groq API for a response.
        completion = client.chat.completions.create(
            model="llama3-70b-8192",  # Specify the AI model to use.
            messages=[{"role": "system", "content": System}] + [{"role": "system", "content": RealtimeInformation()}] + messages,  # Include system instructions, real-time info, and chat history.
            max_tokens=1024,  # Limit the maximum tokens in the response.
            temperature=0.7,  # Adjust response randomness (higher means more random).
            top_p=1,  # Use Nucleus sampling to control diversity.
            stream=True,  # Enable streaming response.
            stop=None  # Allow the model to determine when to stop.
        )

        Answer = ""  # Initialize an empty string to store the AI's response.

        # Process the streamed response chunks.
        for chunk in completion:
            if chunk.choices[0].delta.content:  # Check if there's content in the current chunk.
                Answer += chunk.choices[0].delta.content  # Append the content to the answer.
                Answer = Answer.replace("</s>", "")  # Clean up any unwanted tokens from the response.

        # Append the chatbot's response to the messages list.
        messages.append({"role": "assistant", "content": Answer})

        # Save the updated chat log to the JSON file.
        try:
            with open("Data/ChatLog.json", "w") as f:
                dump(messages, f, indent=4)
        except Exception as e:
            print(f"Error saving chat log: {e}")

        # Return the formatted response.
        return AnswerModifier(Answer=Answer)
    
    except Exception as e:
        error_message = f"Error communicating with Groq API: {e}"
        print(error_message)
        return error_message

# Main program entry point.
if __name__ == "__main__":
    print("Chatbot initialized. Type 'quit' or 'exit' to stop.")
    while True:
        try:
            user_input = input("Enter Your Question: ").strip()  # Prompt the user for a question.
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye!")
                break
            
            # Skip empty input
            if not user_input:
                continue
                
            print(ChatBot(user_input))  # Call the chatbot
            print()  # Add a blank line for better readability
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")