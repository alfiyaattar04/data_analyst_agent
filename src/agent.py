import asyncio
import json
import re
from typing import List, Dict, Any, Union

# Import local modules
from llm_client import GeminiClient
from scraper import WebScraper
from analyzer import DataAnalyzer
from visualizer import ChartGenerator


class DataAnalystAgent:
    def __init__(self):
        self.llm = GeminiClient()
        self.scraper = WebScraper()
        self.analyzer = DataAnalyzer()
        self.visualizer = ChartGenerator()

    async def process_request(self, question_text: str) -> Union[List[Any], Dict[str, Any]]:
        """Main processing pipeline"""
        try:
            # Step 1: Parse the task using LLM
            task_breakdown = await self.llm.parse_task(question_text)

            # Step 2: Handle different data sources
            structured_data = None

            # Check if it's a URL-based task
            url = self.extract_url(question_text)
            if url:
                raw_data = await self.scraper.scrape_url(url)
                structured_data = await self.analyzer.structure_data(raw_data, task_breakdown)

            # Check if it's a DuckDB/SQL query task
            elif 'duckdb' in question_text.lower() or 's3://' in question_text:
                structured_data = await self.analyzer.handle_duckdb_query(question_text)

            # Step 3: Determine response format based on task structure
            is_json_response = self._should_return_json(question_text)

            # Step 4: Process each question/task
            results = []
            result_dict = {}

            tasks = task_breakdown.get('tasks', [])
            if not tasks:
                # Fallback: parse questions directly from text
                tasks = self._extract_questions_from_text(question_text)

            for i, task in enumerate(tasks):
                try:
                    if task['type'] == 'visualization':
                        result = await self.visualizer.generate_chart_with_llm(structured_data, task)
                    else:
                        result = await self.analyzer.analyze_with_llm_code(structured_data, task)

                    if is_json_response:
                        # For JSON response format, use question as key
                        question_key = task.get('question', f'question_{i+1}')
                        result_dict[question_key] = result
                    else:
                        # For array response format
                        results.append(result)

                except Exception as e:
                    error_result = f"Error processing task: {str(e)}"
                    if is_json_response:
                        question_key = task.get('question', f'question_{i+1}')
                        result_dict[question_key] = error_result
                    else:
                        results.append(error_result)

            return result_dict if is_json_response else results

        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            return {"error": error_msg} if self._should_return_json(question_text) else [error_msg]

    def extract_url(self, text: str) -> str:
        """Extract URL from question text"""
        url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
        matches = re.findall(url_pattern, text)
        return matches[0] if matches else None

    def _should_return_json(self, question_text: str) -> bool:
        """Determine if response should be JSON object or array"""
        # Look for indicators of JSON response format
        json_indicators = [
            'respond with a JSON object',
            'JSON object containing',
            'return as JSON',
            '"question":',
            '{"'
        ]
        return any(indicator in question_text for indicator in json_indicators)

    def _extract_questions_from_text(self, text: str) -> List[Dict]:
        """Extract numbered questions from text as fallback"""
        tasks = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if re.match(r'^\d+\.', line):
                # Determine task type
                if 'correlation' in line.lower():
                    task_type = 'correlation'
                elif any(word in line.lower() for word in ['draw', 'plot', 'chart', 'scatterplot', 'graph']):
                    task_type = 'visualization'
                elif any(word in line.lower() for word in ['how many', 'count', 'number of']):
                    task_type = 'numerical'
                else:
                    task_type = 'text'

                tasks.append({
                    'type': task_type,
                    'question': line,
                    'details': ''
                })

        return tasks
