# WhatsApp Chatbot using Green API

This repository contains a WhatsApp chatbot project that utilizes [Green API](https://green-api.com) to interact with WhatsApp messages, fetch conversations, and store them in a Supabase database.

## Features

- Fetch messages from a WhatsApp group or private chat using Green API.
- Store the messages in a Supabase table.
- Filter out unwanted message types (e.g., reactionMessage, quotedMessage, extendedTextMessage, etc.).
- Ignore sensitive data using a `.env` file (never committed to source control).

## Prerequisites

1. **Green API Account**  
   - You need to register at [Green API](https://green-api.com) and obtain your `INSTANCE_ID` and `GREEN_API_TOKEN`.  
   - Make sure the instance is authorized (by scanning the QR code in the Green API dashboard).

2. **Supabase Account & Database**  
   - Sign up at [Supabase](https://supabase.com) (if you haven’t already) and create a project.  
   - Create a table (e.g., `whatsapp_messages`) with the required columns.  
   - Get your `SUPABASE_URL` and `SUPABASE_KEY` from the project’s settings.

3. **Python 3.x**  
   - Make sure you have Python 3.x installed on your local machine.

4. **Git**  
   - To manage your repository locally, you should have [Git](https://git-scm.com/) installed.

## Project Setup

1. **Clone the repository**:
  bash
   git clone https://github.com/<username>/<repo-name>.git
   cd <repo-name>

