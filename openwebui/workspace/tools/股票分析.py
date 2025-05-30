"""
title: 股票分析
description: 一款全面的股票分析工具，可從 Finnhub 免費 API 收集數據並編制詳細報告。
author: changchiyou
author_url: https://github.com/changchiyou
github: https://github.com/changchiyou
original_author: ekatiyar
original_author_url: https://github.com/christ-offer/
original_github: https://github.com/christ-offer/open-webui-tools
funding_url: https://github.com/open-webui
version: 0.0.10
license: MIT
requirements: finnhub-python
"""

import sys
import finnhub
import requests
import aiohttp
import asyncio
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import (
    Dict,
    Any,
    List,
    Union,
    Generator,
    Iterator,
    Tuple,
    Optional,
    Callable,
    Awaitable,
)
from functools import lru_cache


def _format_date(date: datetime) -> str:
    """Helper function to format date for Finnhub API"""
    return date.strftime("%Y-%m-%d")


# Caching for expensive operations
@lru_cache(maxsize=128)
def _get_sentiment_model():
    model_name = "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    return tokenizer, model


def _get_basic_info(client: finnhub.Client, ticker: str) -> Dict[str, Any]:
    """
    Fetch comprehensive company information from Finnhub API.
    """
    profile = client.company_profile2(symbol=ticker)
    basic_financials = client.company_basic_financials(ticker, "all")
    peers = client.company_peers(ticker)

    return {"profile": profile, "basic_financials": basic_financials, "peers": peers}


def _get_current_price(client: finnhub.Client, ticker: str) -> Dict[str, float]:
    """
    Fetch current price and daily change from Finnhub API.
    """
    quote = client.quote(ticker)
    return {
        "current_price": quote["c"],
        "change": quote["dp"],
        "change_amount": quote["d"],
        "high": quote["h"],
        "low": quote["l"],
        "open": quote["o"],
        "previous_close": quote["pc"],
    }


def _get_company_news(client: finnhub.Client, ticker: str) -> List[Dict[str, str]]:
    """
    Fetch recent news articles about the company from Finnhub API.
    Returns a list of dictionaries containing news item details.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    news = client.company_news(ticker, _format_date(start_date), _format_date(end_date))

    news_items = news[:10]  # Get the first 10 news items

    return [{"url": item["url"], "title": item["headline"]} for item in news_items]


async def _async_web_scrape(session: aiohttp.ClientSession, url: str) -> str:
    """
    Scrape and process a web page using r.jina.ai

    :param session: The aiohttp ClientSession to use for the request.
    :param url: The URL of the web page to scrape.
    :return: The scraped and processed content without the Links/Buttons section, or an error message.
    """
    jina_url = f"https://r.jina.ai/{url}"

    headers = {
        "X-No-Cache": "true",
        "X-With-Images-Summary": "true",
        "X-With-Links-Summary": "true",
    }

    try:
        async with session.get(jina_url, headers=headers) as response:
            response.raise_for_status()
            content = await response.text()

        # Extract content and remove Links/Buttons section as its too many tokens
        links_section_start = content.rfind("Images:")
        if links_section_start != -1:
            content = content[:links_section_start].strip()

        return content

    except aiohttp.ClientError as e:
        return f"Error scraping web page: {str(e)}"


# Asynchronous sentiment analysis
async def _async_sentiment_analysis(content: str) -> Dict[str, Union[str, float]]:
    tokenizer, model = _get_sentiment_model()

    inputs = tokenizer(content, return_tensors="pt", truncation=True, max_length=512)

    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    sentiment_scores = probabilities.tolist()[0]

    # Update sentiment labels to match the new model's output
    sentiments = ["Neutral", "Positive", "Negative"]
    sentiment = sentiments[sentiment_scores.index(max(sentiment_scores))]

    confidence = max(sentiment_scores)

    return {"sentiment": sentiment, "confidence": confidence}


# Asynchronous data gathering
async def _async_gather_stock_data(
    client: finnhub.Client, ticker: str
) -> Dict[str, Any]:
    basic_info = _get_basic_info(client, ticker)
    current_price = _get_current_price(client, ticker)
    news_items = _get_company_news(client, ticker)

    async with aiohttp.ClientSession() as session:
        scrape_tasks = [_async_web_scrape(session, item["url"]) for item in news_items]
        contents = await asyncio.gather(*scrape_tasks)

    sentiment_tasks = [
        _async_sentiment_analysis(content) for content in contents if content
    ]
    sentiments = await asyncio.gather(*sentiment_tasks)

    sentiment_results = [
        {
            "url": news_items[i]["url"],
            "title": news_items[i]["title"],
            # "content": contents[i][:500] + "..." if contents[i] and len(contents[i]) > 500 else contents[i],
            "sentiment": sentiment["sentiment"],
            "confidence": sentiment["confidence"],
        }
        for i, sentiment in enumerate(sentiments)
        if contents[i]
    ]

    return {
        "basic_info": basic_info,
        "current_price": current_price,
        "sentiments": sentiment_results,
    }


def _compile_report(data: Dict[str, Any]) -> str:
    """
    Compile gathered data into a comprehensive structured report.
    """
    profile = data["basic_info"]["profile"]
    financials = data["basic_info"]["basic_financials"]
    metrics = financials["metric"]
    peers = data["basic_info"]["peers"]
    price_data = data["current_price"]

    report = f"""
    Comprehensive Stock Analysis Report for {profile['name']} ({profile['ticker']})

    Basic Information:
    Industry: {profile.get('finnhubIndustry', 'N/A')}
    Market Cap: {profile.get('marketCapitalization', 'N/A'):,.0f} M USD
    Share Outstanding: {profile.get('shareOutstanding', 'N/A'):,.0f} M
    Country: {profile.get('country', 'N/A')}
    Exchange: {profile.get('exchange', 'N/A')}
    IPO Date: {profile.get('ipo', 'N/A')}

    Current Trading Information:
    Current Price: ${price_data['current_price']:.2f}
    Daily Change: {price_data['change']:.2f}% (${price_data['change_amount']:.2f})
    Day's Range: ${price_data['low']:.2f} - ${price_data['high']:.2f}
    Open: ${price_data['open']:.2f}
    Previous Close: ${price_data['previous_close']:.2f}

    Key Financial Metrics:
    52 Week High: ${financials['metric'].get('52WeekHigh', 'N/A')}
    52 Week Low: ${financials['metric'].get('52WeekLow', 'N/A')}
    P/E Ratio: {financials['metric'].get('peBasicExclExtraTTM', 'N/A')}
    EPS (TTM): ${financials['metric'].get('epsBasicExclExtraItemsTTM', 'N/A')}
    Return on Equity: {financials['metric'].get('roeRfy', 'N/A')}%
    Debt to Equity: {financials['metric'].get('totalDebtToEquityQuarterly', 'N/A')}
    Current Ratio: {financials['metric'].get('currentRatioQuarterly', 'N/A')}
    Dividend Yield: {financials['metric'].get('dividendYieldIndicatedAnnual', 'N/A')}%

    Peer Companies: {', '.join(peers[:5])}

    Detailed Financial Analysis:

    1. Valuation Metrics:
    P/E Ratio: {metrics.get('peBasicExclExtraTTM', 'N/A')}
    - Interpretation: {'High (may be overvalued)' if metrics.get('peBasicExclExtraTTM', 0) > 25 else 'Moderate' if 15 <= metrics.get('peBasicExclExtraTTM', 0) <= 25 else 'Low (may be undervalued)'}

    P/B Ratio: {metrics.get('pbQuarterly', 'N/A')}
    - Interpretation: {'High' if metrics.get('pbQuarterly', 0) > 3 else 'Moderate' if 1 <= metrics.get('pbQuarterly', 0) <= 3 else 'Low'}

    2. Profitability Metrics:
    Return on Equity: {metrics.get('roeRfy', 'N/A')}%
    - Interpretation: {'Excellent' if metrics.get('roeRfy', 0) > 20 else 'Good' if 15 <= metrics.get('roeRfy', 0) <= 20 else 'Average' if 10 <= metrics.get('roeRfy', 0) < 15 else 'Poor'}

    Net Profit Margin: {metrics.get('netProfitMarginTTM', 'N/A')}%
    - Interpretation: {'Excellent' if metrics.get('netProfitMarginTTM', 0) > 20 else 'Good' if 10 <= metrics.get('netProfitMarginTTM', 0) <= 20 else 'Average' if 5 <= metrics.get('netProfitMarginTTM', 0) < 10 else 'Poor'}

    3. Liquidity and Solvency:
    Current Ratio: {metrics.get('currentRatioQuarterly', 'N/A')}
    - Interpretation: {'Strong' if metrics.get('currentRatioQuarterly', 0) > 2 else 'Healthy' if 1.5 <= metrics.get('currentRatioQuarterly', 0) <= 2 else 'Adequate' if 1 <= metrics.get('currentRatioQuarterly', 0) < 1.5 else 'Poor'}

    Debt-to-Equity Ratio: {metrics.get('totalDebtToEquityQuarterly', 'N/A')}
    - Interpretation: {'Low leverage' if metrics.get('totalDebtToEquityQuarterly', 0) < 0.5 else 'Moderate leverage' if 0.5 <= metrics.get('totalDebtToEquityQuarterly', 0) <= 1 else 'High leverage'}

    4. Dividend Analysis:
    Dividend Yield: {metrics.get('dividendYieldIndicatedAnnual', 'N/A')}%
    - Interpretation: {'High yield' if metrics.get('dividendYieldIndicatedAnnual', 0) > 4 else 'Moderate yield' if 2 <= metrics.get('dividendYieldIndicatedAnnual', 0) <= 4 else 'Low yield'}

    5. Market Performance:
    52-Week Range: ${metrics.get('52WeekLow', 'N/A')} - ${metrics.get('52WeekHigh', 'N/A')}
    Current Price Position: {((price_data['current_price'] - metrics.get('52WeekLow', price_data['current_price'])) / (metrics.get('52WeekHigh', price_data['current_price']) - metrics.get('52WeekLow', price_data['current_price'])) * 100):.2f}% of 52-Week Range

    Beta: {metrics.get('beta', 'N/A')}
    - Interpretation: {'More volatile than market' if metrics.get('beta', 1) > 1 else 'Less volatile than market' if metrics.get('beta', 1) < 1 else 'Same volatility as market'}

    Overall Analysis:
    {profile['name']} shows {'strong' if metrics.get('roeRfy', 0) > 15 and metrics.get('currentRatioQuarterly', 0) > 1.5 else 'moderate' if metrics.get('roeRfy', 0) > 10 and metrics.get('currentRatioQuarterly', 0) > 1 else 'weak'} financial health with {'high' if metrics.get('peBasicExclExtraTTM', 0) > 25 else 'moderate' if 15 <= metrics.get('peBasicExclExtraTTM', 0) <= 25 else 'low'} valuation metrics. The company's profitability is {'excellent' if metrics.get('netProfitMarginTTM', 0) > 20 else 'good' if metrics.get('netProfitMarginTTM', 0) > 10 else 'average' if metrics.get('netProfitMarginTTM', 0) > 5 else 'poor'}, and it has {'low' if metrics.get('totalDebtToEquityQuarterly', 0) < 0.5 else 'moderate' if metrics.get('totalDebtToEquityQuarterly', 0) < 1 else 'high'} financial leverage. Investors should consider these factors along with their investment goals and risk tolerance.


    Recent News and Sentiment Analysis:
    """

    for item in data["sentiments"]:
        report += f"""
    Title: {item['title']}
    URL: {item['url']}
    Sentiment Analysis: {item['sentiment']} (Confidence: {item['confidence']:.2f})

    """
    # Content Preview: {item['content'][:500]}...
    return report

async def noop_event_emitter(event: Any) -> None:
    pass

class Tools:
    class Valves(BaseModel):
        FINNHUB_API_KEY: str = Field(
            default="",
            description="Global Finnhub API key."
        )
    class UserValves(BaseModel):
        USER_FINNHUB_API_KEY: str = Field(
            default="",
            description="Your personal Finnhub API key. Allows for individual API call limits and personalized usage of the tool."
        )

    def __init__(self):
        self.valves = self.Valves()

    async def compile_stock_report(
        self,
        ticker: str,
        __user__: dict = {},
        __event_emitter__: Callable[[Any], Awaitable[None]] = noop_event_emitter
    ) -> str:
        """
        Perform a comprehensive stock analysis and compile a detailed report for a given ticker using Finnhub's API.

        This function gathers various data points including:
        - Basic company information (industry, market cap, etc.)
        - Current trading information (price, daily change, etc.)
        - Key financial metrics (P/E ratio, EPS, ROE, etc.)
        - List of peer companies
        - Recent news articles with sentiment analysis using FinBERT

        The gathered data is then compiled into a structured, easy-to-read report.

        :param ticker: The stock ticker symbol (e.g., "AAPL" for Apple Inc.).
        :return: A comprehensive analysis report of the stock as a formatted string.
        """
        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Initializing client", "done": False},
            }
        )

        self.client = finnhub.Client(api_key=__user__["valves"].USER_FINNHUB_API_KEY \
            if "valves" in __user__ and __user__["valves"].USER_FINNHUB_API_KEY else \
            self.valves.FINNHUB_API_KEY)

        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Retrieving stock data", "done": False},
            }
        )
        data = await _async_gather_stock_data(self.client, ticker)
        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Compiling stock report", "done": False},
            }
        )
        report = _compile_report(data)
        # Get lastest price from data
        last_price = data["current_price"]["current_price"]
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Finished creating report - latest price: "
                    + str(last_price),
                    "done": True,
                },
            }
        )
        return report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("You must provide exactly 2 parameter as FINNHUB_API_KEY, TICKET")
        exit(1)
    tool = Tools()
    tool.valves.FINNHUB_API_KEY = sys.argv[1]

    async def main():
        result = await tool.compile_stock_report(sys.argv[2])
        print(result)

    asyncio.run(main())