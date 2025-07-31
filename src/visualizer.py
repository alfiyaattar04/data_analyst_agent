from .llm_client import GeminiClient
from typing import Dict
import sys
import os
import json
import tempfile
import subprocess
import io
import base64
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend


class ChartGenerator:
    def __init__(self):
        # Set style for better-looking plots
        plt.style.use('default')
        sns.set_palette("husl")
        self.llm = GeminiClient()

    async def generate_chart_with_llm(self, data: pd.DataFrame, task: Dict) -> str:
        """Generate chart using LLM-generated code and return as base64 data URI"""
        try:
            if data is None or data.empty:
                return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

            # Create sample data for LLM
            sample_data = self._create_sample_data(data)

            # Generate visualization code using LLM
            chart_code = await self._generate_chart_code(sample_data, task)

            # Execute the generated code and get base64 image
            base64_image = await self._execute_chart_code(chart_code, data)

            return base64_image

        except Exception as e:
            raise Exception(f"Chart generation failed: {str(e)}")

    def _create_sample_data(self, data: pd.DataFrame) -> Dict:
        """Create sample data representation for LLM"""
        sample = {
            'shape': data.shape,
            'columns': list(data.columns),
            'dtypes': {col: str(dtype) for col, dtype in data.dtypes.items()},
            'sample_rows': data.head(5).to_dict('records'),
            'column_samples': {}
        }

        # Add column statistics
        for col in data.columns:
            try:
                numeric_data = pd.to_numeric(data[col], errors='coerce')
                if numeric_data.notna().sum() > 0:
                    sample['column_samples'][col] = {
                        'type': 'numeric',
                        'min': float(numeric_data.min()),
                        'max': float(numeric_data.max()),
                        'mean': float(numeric_data.mean())
                    }
                else:
                    unique_vals = data[col].dropna().unique()[:10]
                    sample['column_samples'][col] = {
                        'type': 'categorical',
                        'unique_values': [str(v) for v in unique_vals]
                    }
            except:
                sample['column_samples'][col] = {'type': 'unknown'}

        return sample

    async def _generate_chart_code(self, sample_data: Dict, task: Dict) -> str:
        """Generate Python code for chart creation using LLM"""
        prompt = f"""
        Generate Python code to create a chart based on the task and data.

        DATA STRUCTURE:
        - Columns: {sample_data['columns']}
        - Column types: {json.dumps(sample_data['column_samples'], indent=2)}
        - Sample: {json.dumps(sample_data['sample_rows'][:3], indent=2)}

        TASK: {task['question']}
        
        REQUIREMENTS:
        1. DataFrame is loaded as 'df'
        2. Create the exact chart requested (scatterplot, bar chart, etc.)
        3. Handle data cleaning and type conversion
        4. Add proper labels, title, and formatting
        5. Use figsize=(10, 6)
        6. If regression line requested, add it with correct color/style
        7. Save plot to SAVE_PATH variable
        8. Use plt.close() after saving
        9. Set DPI=100 for good quality
        10. Handle missing data gracefully

        CRITICAL: For scatterplot with regression line, use numpy.polyfit and numpy.poly1d

        Generate Python code only:
        """

        try:
            response = await self.llm.generate_content(prompt)
            code = self._extract_code_from_response(response.text)
            return code

        except Exception as e:
            raise Exception(f"Chart code generation failed: {str(e)}")

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

        # Extract code-like lines
        lines = response_text.strip().split('\n')
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith(('import ', 'from ', 'plt.', 'sns.', 'df', '#')) or
                '=' in stripped or
                    stripped.startswith(('if ', 'for ', 'while ', 'def ', 'try:', 'except'))):
                code_lines.append(line)

        return '\n'.join(code_lines)

    async def _execute_chart_code(self, code: str, data: pd.DataFrame) -> str:
        """Execute the generated chart code and return base64 encoded image"""
        try:
            # Save data and create temp files
            data_path = self._save_temp_data(data)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as code_file:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_file:
                    img_path = img_file.name

                # Create the full code
                full_code = f"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Load the data
df = pd.read_csv('{data_path}')

# Set the save path
SAVE_PATH = '{img_path}'

# Generated chart code
{code}

print("Chart saved successfully")
"""
                code_file.write(full_code)
                code_file_path = code_file.name

            # Execute the code
            result = subprocess.run(
                [sys.executable, code_file_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Clean up
            os.unlink(code_file_path)
            os.unlink(data_path)

            if result.returncode != 0:
                raise Exception(f"Chart generation failed: {result.stderr}")

            # Read and encode the image
            if os.path.exists(img_path):
                with open(img_path, 'rb') as img_file:
                    img_data = img_file.read()
                    base64_image = base64.b64encode(img_data).decode()

                os.unlink(img_path)

                # Check size (under 100KB)
                if len(base64_image) > 100000:
                    base64_image = await self._compress_image(base64_image)

                return f"data:image/png;base64,{base64_image}"
            else:
                raise Exception("Chart image was not generated")

        except subprocess.TimeoutExpired:
            raise Exception("Chart generation timeout")
        except Exception as e:
            raise Exception(f"Chart execution error: {str(e)}")

    def _save_temp_data(self, data: pd.DataFrame) -> str:
        """Save DataFrame to temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            data.to_csv(temp_file.name, index=False)
            return temp_file.name

    async def _compress_image(self, base64_image: str) -> str:
        """Compress image if it's too large"""
        try:
            from PIL import Image
            import io

            # Decode base64 to image
            img_data = base64.b64decode(base64_image)
            img = Image.open(io.BytesIO(img_data))

            # Reduce quality/size
            output = io.BytesIO()
            img.save(output, format='PNG', optimize=True, quality=70)
            compressed_data = output.getvalue()

            return base64.b64encode(compressed_data).decode()

        except Exception:
            # If compression fails, truncate
            return base64_image[:100000] if len(base64_image) > 100000 else base64_image
