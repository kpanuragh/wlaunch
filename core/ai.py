import google.generativeai as genai
from core.config import get_api_key

class AIHandler:
    def __init__(self):
        self.api_key = get_api_key()
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None

    def is_configured(self):
        # Refresh key in case it was added at runtime
        if not self.model:
            self.api_key = get_api_key()
            if self.api_key:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
        return self.model is not None

    def ask(self, prompt):
        if not self.is_configured():
            return "Error: Gemini API Key not found in ~/.config/wlaunch/config.json"
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"
