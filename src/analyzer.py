import sys
import pandas as pd
import numpy as np
import subprocess
import tempfile
import json
import os
import duckdb
from typing import Any, Dict, List
from .llm_client import GeminiClient


class DataAnalyzer:
    def __init__(self):
        self.data = None
        self.llm = GeminiClient()

    async def structure_data(self, html_content: str, task_info: Dict) -> pd.DataFrame:
        """Convert scraped HTML to structured data"""
        from .scraper import WebScraper
        from bs4 import BeautifulSoup
        scraper = WebScraper()

        # Extract tables from HTML
        tables = scraper.extract_tables(html_content)

        if not tables:
            # If no tables, try to extract other structured data
            soup = BeautifulSoup(html_content, 'html.parser')
            structured_content = self._extract_structured_content(soup)
            if structured_content:
                return pd.DataFrame(structured_content)
            else:
                raise Exception("No structured data found in scraped content")

        # Find the most relevant table
        main_table = self._select_best_table(tables, task_info)

        # Clean column names and data
        main_table = self._clean_dataframe(main_table)

        self.data = main_table
        return main_table

    async def handle_duckdb_query(self, question_text: str) -> pd.DataFrame:
        """Handle DuckDB queries for remote data"""
        try:
            # Extract the SQL query from the question
            sql_query = self._extract_sql_query(question_text)
            if not sql_query:
                raise Exception("No SQL query found in the request")

            # Execute DuckDB query
            conn = duckdb.connect()

            # Install and load extensions
            conn.execute("INSTALL httpfs; LOAD httpfs;")
            conn.execute("INSTALL parquet; LOAD parquet;")

            # Execute the query
            result = conn.execute(sql_query).fetchdf()
            conn.close()

            return result

        except Exception as e:
            raise Exception(f"DuckDB query failed: {str(e)}")

    def _extract_sql_query(self, text: str) -> str:
        """Extract SQL query from text"""
        import re

        # Look for SQL code blocks
        sql_blocks = re.findall(r'```sql\n(.*?)\n```',
                                text, re.DOTALL | re.IGNORECASE)
        if sql_blocks:
            return sql_blocks[0].strip()

        # Look for SELECT statements
        select_matches = re.findall(
            r'(SELECT.*?;)', text, re.DOTALL | re.IGNORECASE)
        if select_matches:
            return select_matches[0].strip()

        return None

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare DataFrame"""
        # Clean column names
        df.columns = df.columns.astype(str)
        df.columns = [col.strip().replace('\n', ' ').replace('\r', '')
                      for col in df.columns]

        # Remove completely empty rows
        df = df.dropna(how='all')

        # Clean string columns
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace('nan', '')

        return df

    async def analyze_with_llm_code(self, data: pd.DataFrame, task: Dict) -> Any:
        """Generate and execute code using LLM for specific analysis task"""
        try:
            if data is None or data.empty:
                return "No data available for analysis"

            # Create sample data for LLM
            sample_data = self._create_sample_data(data)

            # Generate analysis code using LLM
            analysis_code = await self._generate_analysis_code(sample_data, task)

            # Execute the generated code
            result = await self._execute_analysis_code(analysis_code, data)

            return result

        except Exception as e:
            raise Exception(f"LLM-based analysis failed: {str(e)}")

    def _create_sample_data(self, data: pd.DataFrame) -> Dict:
        """Create sample data representation for LLM"""
        sample = {
            'shape': data.shape,
            'columns': list(data.columns),
            'dtypes': {col: str(dtype) for col, dtype in data.dtypes.items()},
            'sample_rows': data.head(10).to_dict('records'),
            'column_samples': {}
        }

        # Add unique values for categorical columns
        for col in data.columns:
            if data[col].dtype == 'object':
                unique_vals = data[col].dropna().unique()[:20]
                sample['column_samples'][col] = list(unique_vals)

        return sample

    async def _generate_analysis_code(self, sample_data: Dict, task: Dict) -> str:
        """Generate Python code using LLM for the specific analysis task"""
        prompt = f"""
        You are a data analysis code generator. Generate Python code that performs the exact analysis requested.

        SAMPLE DATA:
        - Shape: {sample_data['shape']}
        - Columns: {sample_data['columns']}
        - Sample rows: {json.dumps(sample_data['sample_rows'][:3], indent=2)}

        TASK: {task['question']}
        TASK TYPE: {task['type']}

        CRITICAL REQUIREMENTS:
        1. The DataFrame is already loaded as 'df'
        2. Import all necessary libraries (pandas, numpy, etc.)
        3. Handle missing/invalid data gracefully
        4. Convert data types as needed (strings to numbers, dates, etc.)
        5. Return final result as 'result' variable
        6. For numerical answers, return int or float
        7. For text answers, return string
        8. For correlations, return float rounded to 6 decimals
        9. Be precise with data filtering and calculations
        10. Handle edge cases (empty data, no matches, etc.)

        EXAMPLES:
        - For "How many X before Y?": Count rows where condition is met
        - For "Which is the earliest X?": Find row with minimum date/year
        - For "What's the correlation?": Calculate correlation coefficient
        
        Generate clean, working Python code:
        """

        try:
            response = await self.llm.generate_content(prompt)
            code = self._extract_code_from_response(response.text)
            return code

        except Exception as e:
            raise Exception(f"Code generation failed: {str(e)}")

    def _extract_code_from_response(self, response_text: str) -> str:
        """Extract Python code from LLM response"""
        import re

        # Try to find code blocks
        code_blocks = re.findall(
            r'```python\n(.*?)\n```', response_text, re.DOTALL)
        if code_blocks:
            return code_blocks[0]

        code_blocks = re.findall(r'```\n(.*?)\n```', response_text, re.DOTALL)
        if code_blocks:
            return code_blocks[0]

        # Extract likely code lines
        lines = response_text.strip().split('\n')
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith(('import ', 'from ', 'df', 'result', '#')) or
                '=' in stripped or
                    stripped.startswith(('if ', 'for ', 'while ', 'def ', 'try:', 'except'))):
                code_lines.append(line)

        return '\n'.join(code_lines)

    async def _execute_analysis_code(self, code: str, data: pd.DataFrame) -> Any:
        """Execute the generated analysis code safely"""
        try:
            # Save data to temporary file
            data_path = self._save_temp_data(data)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as code_file:
                full_code = f"""
import pandas as pd
import numpy as np
import json
import sys
from datetime import datetime
import re
import warnings
warnings.filterwarnings('ignore')

# Load the data
df = pd.read_csv('{data_path}')

# Generated analysis code
{code}

# Output result
if isinstance(result, (int, float, str, bool)):
    print(json.dumps({{'result': result, 'type': str(type(result).__name__)}}))
else:
    print(json.dumps({{'result': str(result), 'type': str(type(result).__name__)}}))
"""
                code_file.write(full_code)
                code_file_path = code_file.name

            # Execute the code
            result = subprocess.run(
                [sys.executable, code_file_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Clean up
            os.unlink(code_file_path)
            os.unlink(data_path)

            if result.returncode != 0:
                raise Exception(f"Code execution failed: {result.stderr}")

            # Parse result
            try:
                output = json.loads(result.stdout.strip())
                return output['result']
            except json.JSONDecodeError:
                return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise Exception("Analysis code execution timeout")
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")

    def _save_temp_data(self, data: pd.DataFrame) -> str:
        """Save DataFrame to temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            data.to_csv(temp_file.name, index=False)
            return temp_file.name

    def _select_best_table(self, tables: List[pd.DataFrame], task_info: Dict) -> pd.DataFrame:
        """Select the most relevant table from multiple tables"""
        if len(tables) == 1:
            return tables[0]

        best_table = None
        best_score = 0

        for table in tables:
            score = 0

            # Size factor
            score += len(table) * 0.1
            score += len(table.columns) * 0.05

            # Content relevance
            for col in table.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['rank', 'name', 'title', 'year', 'gross', 'revenue']):
                    score += 10

            if score > best_score:
                best_score = score
                best_table = table

        return best_table or tables[0]

    def _extract_structured_content(self, soup) -> List[Dict]:
        """Extract structured content from non-table elements"""
        structured_data = []

        # Try to find structured lists
        lists = soup.find_all(['ul', 'ol'])
        for lst in lists:
            items = lst.find_all('li')
            if len(items) > 5:
                for item in items:
                    text = item.get_text(strip=True)
                    if text:
                        parsed_item = self._parse_list_item(text)
                        if parsed_item:
                            structured_data.append(parsed_item)

        return structured_data

    def _parse_list_item(self, text: str) -> Dict:
        """Parse individual list items for structured data"""
        import re
        item = {'text': text}

        # Extract numbers
        numbers = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', text)
        if numbers:
            item['numbers'] = numbers

        # Extract years
        years = re.findall(r'\b(19|20)\d{2}\b', text)
        if years:
            item['years'] = years

        return item
