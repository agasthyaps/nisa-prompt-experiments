# Chat Arena v2

A Streamlit-based application for comparing AI assistants in a blind test format. Users can chat with two randomly selected AI configurations and vote on which provides better responses.

## Features

- **Blind Testing**: Two AI assistants with randomly assigned models and system prompts compete side-by-side
- **Password-Protected Settings**: Administrators can manage system prompts through a secure settings panel
- **Persistent Prompt Management**: System prompts are stored in JSON format and persist across sessions
- **Multi-Modal Support**: Upload images along with text messages (for vision-capable models)
- **Vote Tracking**: All conversations and voting results are saved for analysis

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure OpenAI API Key**
   Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. **Run the Application**
   ```bash
   streamlit run chat_arena_v2.py
   ```

## Usage

### For Users

1. Click "Start New Conversation" to begin
2. Type messages and optionally upload images
3. Both assistants will respond simultaneously
4. When done chatting, click "End & Vote"
5. Vote for the assistant that provided better responses
6. The identities of the assistants will be revealed after voting

### For Administrators

1. Click the gear icon (⚙️) in the top-left corner
2. Enter the password: `admin123` (change this in production!)
3. In the settings panel, you can:
   - View and edit existing system prompts
   - Add new system prompts
   - Delete prompts (with confirmation)
   - All changes are saved to `data/system_prompts.json`

## File Structure

```
├── chat_arena_v2.py      # Main application
├── data/
│   ├── system_prompts.json  # Persistent prompt storage
│   └── votes.json          # Vote history
├── .env                    # API key configuration
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Configuration

### Models
The application randomly selects from these models:
- GPT-4
- GPT-4 Turbo
- GPT-3.5 Turbo

You can modify the `MODELS` list in `chat_arena_v2.py` to add or remove models.

### Default System Prompts
Three default prompts are included:
- Helpful Assistant
- Creative Writer  
- Technical Expert

These can be modified or expanded through the settings interface.

### Security
- Settings password is hardcoded as `admin123` - **change this for production use**
- Consider implementing proper authentication for production deployments
- API keys should never be committed to version control

## Data Storage

- **System Prompts**: Stored in `data/system_prompts.json`
- **Votes**: Stored in `data/votes.json` with timestamps and full conversation history
- Both files are created automatically if they don't exist

## Tips

- The application works best with models that support the chat completion API
- For image uploads, ensure you're using vision-capable models (e.g., GPT-4V)
- System prompts should be clear and distinct to create meaningful comparisons
- Regular backups of the `data/` directory are recommended

---

Enjoy tinkering! ✨ 