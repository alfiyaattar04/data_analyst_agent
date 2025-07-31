# Data Analyst Agent

A powerful API that uses LLMs to source, prepare, analyze, and visualize any data.

## Features

- **Web Scraping**: Automatically scrapes data from URLs (Wikipedia, etc.)
- **Data Analysis**: Uses LLM-generated code for complex analysis tasks
- **Visualization**: Creates charts and plots with base64 encoding
- **Remote Data**: Supports DuckDB queries for S3/remote datasets
- **Flexible Input**: Handles various question formats and data sources

## Project Structure

```
/
├── src/
│   ├── __init__.py
│   ├── agent.py          # Main processing pipeline
│   ├── llm_client.py     # Gemini LLM client
│   ├── scraper.py        # Web scraping with Playwright
│   ├── analyzer.py       # Data analysis with LLM-generated code
│   └── visualizer.py     # Chart generation
├── api/
│   └── index.py          # Flask API endpoint
├── requirements.txt
├── .env
├── vercel.json
└── README.md
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Set Environment Variables

Create a `.env` file or set the environment variable:

```bash
export GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Run Locally

```bash
python api/index.py
```

The API will be available at `http://localhost:5000/api/`

## API Usage

### Endpoint: POST /api/

Send analysis tasks via POST request:

#### File Upload:

```bash
curl "http://localhost:5000/api/" -F "file=@question.txt"
```

#### Direct Text:

```bash
curl "http://localhost:5000/api/" -H "Content-Type: text/plain" -d "Your analysis question here"
```

#### JSON:

```bash
curl "http://localhost:5000/api/" -H "Content-Type: application/json" -d '{"question": "Your analysis question"}'
```

## Sample Questions

### Wikipedia Analysis (Array Response):

```
Scrape the list of highest grossing films from Wikipedia:
https://en.wikipedia.org/wiki/List_of_highest-grossing_films

Answer the following questions and respond with a JSON array of strings containing the answer.

1. How many $2 bn movies were released before 2020?
2. Which is the earliest film that grossed over $1.5 bn?
3. What's the correlation between the Rank and Peak?
4. Draw a scatterplot of Rank and Peak along with a dotted red regression line through it.
   Return as a base-64 encoded data URI, `"data:image/png;base64,iVBORw0KG..."` under 100,000 bytes.
```

**Expected Response:** `[1, "Titanic", 0.485782, "data:image/png;base64,..."]`

### Remote Data Analysis (JSON Response):

```
Answer the following questions and respond with a JSON object containing the answer.

{
  "Which high court disposed the most cases from 2019 - 2022?": "...",
  "What's the regression slope of the date_of_registration - decision_date by year in the court=33_10?": "...",
  "Plot the year and # of days of delay from the above question as a scatterplot with a regression line. Encode as a base64 data URI under 100,000 characters": "data:image/webp:base64,..."
}
```

## Response Formats

The agent automatically detects the expected response format:

- **Array Response**: `[result1, result2, result3, "data:image/png;base64,..."]`
- **JSON Response**: `{"question1": "answer1", "question2": "answer2"}`

## Deployment

### Vercel (Recommended):

1. Push code to GitHub
2. Connect repository to Vercel
3. Add `GEMINI_API_KEY` environment variable in Vercel dashboard
4. Deploy

### Railway/Render:

1. Connect GitHub repository
2. Set `GEMINI_API_KEY` environment variable
3. Deploy

### Local Testing:

```bash
python api/index.py
# API available at http://localhost:5000/api/
```

## How It Works

1. **Task Parsing**: LLM analyzes the input and breaks it into structured tasks
2. **Data Sourcing**:
   - Scrapes URLs using Playwright
   - Executes DuckDB queries for remote data
3. **Data Analysis**: Generates and executes Python code using LLM
4. **Visualization**: Creates charts with matplotlib/seaborn and encodes as base64
5. **Response Formatting**: Returns results in requested format (array or JSON)

## Key Components

- **GeminiClient**: Handles LLM interactions for task parsing and code generation
- **WebScraper**: Uses Playwright for robust web scraping
- **DataAnalyzer**: Generates and executes analysis code safely in subprocess
- **ChartGenerator**: Creates visualizations with proper formatting and compression
- **DataAnalystAgent**: Orchestrates the entire pipeline

## Error Handling

- Graceful fallbacks for LLM failures
- Safe code execution in isolated processes
- Comprehensive error messages
- Timeout protection for long-running operations

## Limitations

- Requires stable internet connection for LLM and web scraping
- Gemini API rate limits may apply
- Chart generation limited to 100KB base64 images
- DuckDB queries require proper S3 permissions

## License

MIT License
