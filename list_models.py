
import google.generativeai as genai
import os

GEMINI_API_KEY = "AIzaSyCz3XcAR3NbM10NZcEa7PXziBYuaHGHY7g"
genai.configure(api_key=GEMINI_API_KEY)

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
