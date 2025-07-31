import google.generativeai as genai
import json
import os
import re
from typing import Dict, Any


class GeminiClient:
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    async def generate_content(self, prompt: str) -> Any:
        """Generate content using Gemini"""
        try:
            response = self.model.generate_content(prompt)
            return response
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")

    async def parse_task(self, question_text: str) -> Dict[str, Any]:
        """Parse the input task into structured format"""
        prompt = f"""
        Analyze this data analysis request and break it down into structured tasks:
        
        {question_text}
        
        Return a JSON object with this structure:
        {{
            "data_source": "URL or description of data source",
            "tasks": [
                {{
                    "type": "numerical|text|correlation|visualization",
                    "question": "the specific question",
                    "details": "additional details for processing"
                }}
            ]
        }}
        
        Task types:
        - numerical: Questions asking for counts, numbers, calculations
        - text: Questions asking for names, titles, or text responses
        - correlation: Questions about relationships between variables
        - visualization: Requests for charts, plots, graphs
        
        Extract the exact questions as they appear in the text.
        """

        try:
            response = await self.generate_content(prompt)
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._fallback_parse(question_text)
        except Exception as e:
            return self._fallback_parse(question_text)

    def _fallback_parse(self, question_text: str) -> Dict[str, Any]:
        """Fallback parsing if LLM fails"""
        tasks = []
        lines = question_text.split('\n')

        for line in lines:
            line = line.strip()
            if re.match(r'^\d+\.', line):
                if 'correlation' in line.lower():
                    task_type = 'correlation'
                elif any(word in line.lower() for word in ['draw', 'plot', 'chart', 'scatterplot']):
                    task_type = 'visualization'
                elif any(word in line.lower() for word in ['how many', 'count']):
                    task_type = 'numerical'
                else:
                    task_type = 'text'

                tasks.append({
                    'type': task_type,
                    'question': line,
                    'details': ''
                })

        url = self._extract_url_from_text(question_text)
        return {
            'data_source': url or 'unknown',
            'tasks': tasks
        }

    def _extract_url_from_text(self, text: str) -> str:
        """Extract URL from question text"""
        url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
        matches = re.findall(url_pattern, text)
        return matches[0] if matches else None
