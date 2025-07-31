from typing import List
from playwright.async_api import async_playwright
import pandas as pd
from bs4 import BeautifulSoup
import asyncio


class WebScraper:
    def __init__(self):
        self.browser = None
        self.context = None

    async def scrape_url(self, url: str) -> str:
        """Scrape content from URL using Playwright"""
        async with async_playwright() as p:
            # Launch browser (headless for production)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()

            try:
                # Navigate to URL with longer timeout
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait a bit for dynamic content
                await page.wait_for_timeout(2000)

                # Get page content
                content = await page.content()

                await browser.close()
                return content

            except Exception as e:
                await browser.close()
                raise Exception(f"Scraping failed for {url}: {str(e)}")

    def extract_tables(self, html_content: str) -> List[pd.DataFrame]:
        """Extract tables from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table')

        dataframes = []
        for table in tables:
            try:
                # Try pandas read_html first
                df = pd.read_html(str(table))[0]
                if len(df) > 1:  # Only keep tables with multiple rows
                    dataframes.append(df)
            except:
                # Fallback: manual table parsing
                try:
                    df = self._manual_table_parse(table)
                    if df is not None and len(df) > 1:
                        dataframes.append(df)
                except:
                    continue

        return dataframes

    def _manual_table_parse(self, table) -> pd.DataFrame:
        """Manually parse table when pandas fails"""
        rows = []
        headers = []

        # Extract headers
        header_row = table.find('tr')
        if header_row:
            headers = [th.get_text(strip=True)
                       for th in header_row.find_all(['th', 'td'])]

        # Extract data rows
        for row in table.find_all('tr')[1:]:  # Skip header row
            cells = [td.get_text(strip=True)
                     for td in row.find_all(['td', 'th'])]
            if cells:
                rows.append(cells)

        if headers and rows:
            # Ensure all rows have same length as headers
            max_cols = len(headers)
            cleaned_rows = []
            for row in rows:
                # Pad or trim row to match header length
                if len(row) < max_cols:
                    row.extend([''] * (max_cols - len(row)))
                elif len(row) > max_cols:
                    row = row[:max_cols]
                cleaned_rows.append(row)

            return pd.DataFrame(cleaned_rows, columns=headers)

        return None
