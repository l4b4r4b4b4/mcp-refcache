import logging
import requests
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator
from mcp.server.fastmcp import FastMCP
from toolsets.servers.cache import ToolsetCache, CacheReference

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Crypto_API")

# Create FastMCP server with proper metadata
mcp = FastMCP(
    name="Cryptocurrency Data Tools",
    description="Tools to access cryptocurrency pricing, trends, and market data with support for result referencing",
    version="1.1.0",
    dependencies=["requests", "pydantic"],
    author="Crypto Research Team",
    tags=["cryptocurrency", "finance", "market-data", "reference"],
)

# CoinGecko API base URL
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Create caches with optimized settings to minimize API calls
coin_info_cache = ToolsetCache(
    name="crypto.coin_info",
    deterministic=False,
    expiry_seconds=1800,
    max_size=1000,
)

price_cache = ToolsetCache(
    name="crypto.prices",
    deterministic=False,
    expiry_seconds=300,
    max_size=2000,
)

historical_cache = ToolsetCache(
    name="crypto.historical",
    deterministic=True,
    max_size=5000,
)

market_cache = ToolsetCache(
    name="crypto.market",
    deterministic=False,
    expiry_seconds=900,
    max_size=2000,
)

search_cache = ToolsetCache(
    name="crypto.search",
    deterministic=True,
    max_size=10000,
)


# Helper function to handle rate limits
def rate_limited_request(url, params=None):
    try:
        response = requests.get(url, params=params)
        # If rate limited, log it but don't retry automatically (rely on cache)
        if response.status_code == 429:
            logger.warning("Rate limit hit. Using cached data if available.")
            raise ValueError("Rate limit exceeded. Try again in a minute.")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        raise


# ---- PYDANTIC MODELS FOR INPUT VALIDATION ----


class CoinIdRequest(BaseModel):
    coin_id: Union[str, CacheReference] = Field(
        ...,
        description="The ID of the coin on CoinGecko (e.g., 'bitcoin', 'ethereum') or a reference to a previous result",
        examples=["bitcoin", "ethereum", "solana"],
    )

    @validator("coin_id")
    def validate_coin_id(cls, v):
        if isinstance(v, str) and len(v) < 1:
            raise ValueError("Coin ID must not be empty")
        if isinstance(v, str) and len(v) > 100:
            raise ValueError("Coin ID must not exceed 100 characters")
        return v


class CoinPriceRequest(BaseModel):
    coin_ids: Union[str, CacheReference] = Field(
        ...,
        description="Comma-separated list of coin IDs (e.g., 'bitcoin,ethereum') or a reference to a previous result",
        examples=["bitcoin", "bitcoin,ethereum,solana"],
    )
    vs_currencies: str = Field(
        "usd",
        description="Comma-separated list of currencies (e.g., 'usd,eur')",
        examples=["usd", "usd,eur,jpy"],
    )

    @validator("coin_ids")
    def validate_coin_ids(cls, v):
        if isinstance(v, str) and len(v) < 1:
            raise ValueError("Coin IDs must not be empty")
        return v


class HistoricalPriceRequest(BaseModel):
    coin_id: Union[str, CacheReference] = Field(
        ...,
        description="The ID of the coin on CoinGecko (e.g., 'bitcoin', 'ethereum') or a reference to a previous result",
        examples=["bitcoin", "ethereum"],
    )
    days: int = Field(
        30,
        description="Number of days of data to retrieve (1-365)",
        ge=1,
        le=365,
        examples=[7, 30, 90],
    )
    vs_currency: str = Field(
        "usd",
        description="Currency to get prices in (e.g., 'usd', 'eur')",
        examples=["usd", "eur", "jpy"],
    )

    @validator("coin_id")
    def validate_coin_id(cls, v):
        if isinstance(v, str) and len(v) < 1:
            raise ValueError("Coin ID must not be empty")
        if isinstance(v, str) and len(v) > 100:
            raise ValueError("Coin ID must not exceed 100 characters")
        return v


class SearchRequest(BaseModel):
    query: Union[str, CacheReference] = Field(
        ...,
        description="Search query string or a reference to a previous result",
        examples=["bitcoin", "defi", "exchange token"],
    )

    @validator("query")
    def validate_query(cls, v):
        if isinstance(v, str) and len(v) < 1:
            raise ValueError("Search query must not be empty")
        if isinstance(v, str) and len(v) > 100:
            raise ValueError("Search query must not exceed 100 characters")
        return v


class TopCoinsRequest(BaseModel):
    vs_currency: str = Field(
        "usd",
        description="The currency to show prices in (e.g., 'usd', 'eur')",
        examples=["usd", "eur", "btc"],
    )
    count: int = Field(
        10,
        description="Number of top coins to return (1-250)",
        ge=1,
        le=250,
        examples=[10, 25, 100],
    )


class ReturnTypeParam(BaseModel):
    return_type: Literal["full", "preview", "reference"] = Field(
        "full",
        description="Controls how results are returned: 'full' for complete results, 'preview' for a summary, 'reference' for a reference ID that can be used in subsequent calls",
    )


# ---- TOOLS ----


@mcp.tool(
    description="Get detailed information about a specific cryptocurrency including price, market data, and descriptions.",
)
@coin_info_cache.cached
def get_coin_info(
    request: CoinIdRequest, options: Optional[ReturnTypeParam] = None
) -> Union[Dict[str, Any], str, CacheReference]:
    """
    Get detailed information about a specific cryptocurrency.

    Parameters:
    - request: The cryptocurrency to get information about
      - coin_id: The ID of the coin on CoinGecko (e.g., 'bitcoin', 'ethereum') or a reference
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete data (default)
      - return_type="preview": Return a text preview of the data
      - return_type="reference": Return a reference ID that can be used in other tool calls

    You can pass a CacheReference object instead of a literal value for the coin_id parameter
    to use a previously cached result. For example, you can use a search result reference
    to get information about a coin found in a search.

    Examples:
    ```
    # Basic usage
    get_coin_info(request={"coin_id": "bitcoin"})

    # Using a reference from a search result
    get_coin_info(request={"coin_id": <search_result_reference>})

    # Getting a reference to use in another call
    get_coin_info(
        request={"coin_id": "ethereum"},
        options={"return_type": "reference"}
    )
    ```

    Returns:
    - With return_type="full": Complete coin information (dictionary)
    - With return_type="preview": A string summary of the coin information
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    logger.debug(f"Getting information for coin: {request.coin_id}")

    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    # Process coin_id (handle references)
    coin_id = request.coin_id
    if isinstance(coin_id, CacheReference):
        resolved_value = coin_info_cache.resolve_reference(coin_id)
        if isinstance(resolved_value, dict) and "id" in resolved_value:
            # If the reference resolves to a coin info object, extract the ID
            coin_id = resolved_value["id"]
        elif isinstance(resolved_value, str):
            # If the reference resolves to a string, use it directly
            coin_id = resolved_value
        else:
            # Try to convert to string
            coin_id = str(resolved_value)

    url = f"{COINGECKO_API_URL}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "true",
    }

    try:
        data = rate_limited_request(url, params)

        result = {
            "id": data.get("id"),
            "name": data.get("name"),
            "symbol": data.get("symbol"),
            "current_price": data.get("market_data", {})
            .get("current_price", {})
            .get("usd"),
            "market_cap": data.get("market_data", {}).get("market_cap", {}).get("usd"),
            "total_volume": data.get("market_data", {})
            .get("total_volume", {})
            .get("usd"),
            "high_24h": data.get("market_data", {}).get("high_24h", {}).get("usd"),
            "low_24h": data.get("market_data", {}).get("low_24h", {}).get("usd"),
            "price_change_24h": data.get("market_data", {}).get("price_change_24h"),
            "price_change_percentage_24h": data.get("market_data", {}).get(
                "price_change_percentage_24h"
            ),
            "market_cap_rank": data.get("market_cap_rank"),
            "description": data.get("description", {}).get("en", ""),
            "homepage": data.get("links", {}).get("homepage", [""])[0],
            "github": data.get("links", {}).get("repos_url", {}).get("github", []),
            "categories": data.get("categories"),
        }

        logger.info(
            f"Successfully retrieved info for {result['name']} ({result['symbol']})"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to get coin info: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get coin info: {str(e)}")


@mcp.tool(
    description="Get current prices for one or multiple cryptocurrencies with 24h market data."
)
@price_cache.cached
def get_coin_price(
    request: CoinPriceRequest, options: Optional[ReturnTypeParam] = None
) -> Union[Dict[str, Any], str, CacheReference]:
    """
    Get current prices for one or multiple cryptocurrencies.

    Parameters:
    - request: The cryptocurrencies and currencies to get prices for
      - coin_ids: Comma-separated list of coin IDs (e.g., 'bitcoin,ethereum') or a reference
      - vs_currencies: Comma-separated list of currencies (e.g., 'usd,eur')
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete price data (default)
      - return_type="preview": Return a text preview of the data
      - return_type="reference": Return a reference ID that can be used in other tool calls

    You can pass a CacheReference object instead of a literal value for the coin_ids parameter
    to use a previously cached result.

    Examples:
    ```
    # Basic usage
    get_coin_price(request={"coin_ids": "bitcoin,ethereum", "vs_currencies": "usd,eur"})

    # Using a reference from another tool
    get_coin_price(request={"coin_ids": <coin_reference>, "vs_currencies": "usd"})

    # Getting a reference to use in another call
    get_coin_price(
        request={"coin_ids": "bitcoin", "vs_currencies": "usd"},
        options={"return_type": "reference"}
    )
    ```

    Returns:
    - With return_type="full": Complete price data (dictionary)
    - With return_type="preview": A string summary of the price data
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    # Process coin_ids (handle references)
    coin_ids = request.coin_ids
    if isinstance(coin_ids, CacheReference):
        resolved_value = price_cache.resolve_reference(coin_ids)
        if isinstance(resolved_value, dict) and "id" in resolved_value:
            # If the reference resolves to a coin info object, extract the ID
            coin_ids = resolved_value["id"]
        elif isinstance(resolved_value, str):
            # If the reference resolves to a string, use it directly
            coin_ids = resolved_value
        else:
            # Try to convert to string
            coin_ids = str(resolved_value)

    logger.debug(
        f"Getting prices for coins: {coin_ids} in currencies: {request.vs_currencies}"
    )

    url = f"{COINGECKO_API_URL}/simple/price"
    params = {
        "ids": coin_ids,
        "vs_currencies": request.vs_currencies,
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
    }

    try:
        data = rate_limited_request(url, params)
        logger.info(f"Successfully retrieved prices for {len(data)} coins")
        return data

    except Exception as e:
        logger.error(f"Failed to get prices: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get prices: {str(e)}")


@mcp.tool(description="Get a list of trending coins in the last 24 hours.")
@market_cache.cached
def get_trending_coins(
    options: Optional[ReturnTypeParam] = None,
) -> Union[Dict[str, Any], str, CacheReference]:
    """
    Get a list of trending coins in the last 24 hours.

    Parameters:
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete trending data (default)
      - return_type="preview": Return a text preview of the data
      - return_type="reference": Return a reference ID that can be used in other tool calls

    Examples:
    ```
    # Basic usage
    get_trending_coins()

    # Getting a reference to use in another call
    get_trending_coins(options={"return_type": "reference"})

    # Getting a preview of the data
    get_trending_coins(options={"return_type": "preview"})
    ```

    Returns:
    - With return_type="full": Complete trending coin data (dictionary)
    - With return_type="preview": A string summary of the trending coins
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    logger.debug("Getting trending coins")

    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    url = f"{COINGECKO_API_URL}/search/trending"

    try:
        data = rate_limited_request(url)

        result = {
            "coins": [
                {
                    "id": coin["item"]["id"],
                    "name": coin["item"]["name"],
                    "symbol": coin["item"]["symbol"],
                    "market_cap_rank": coin["item"]["market_cap_rank"],
                    "score": coin["item"]["score"],
                }
                for coin in data.get("coins", [])
            ]
        }

        logger.info(f"Successfully retrieved {len(result['coins'])} trending coins")
        return result

    except Exception as e:
        logger.error(f"Failed to get trending coins: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get trending coins: {str(e)}")


@mcp.tool(
    description="Get cryptocurrency global market data including market cap, volume, and dominance metrics."
)
@market_cache.cached
def get_global_market_data(
    options: Optional[ReturnTypeParam] = None,
) -> Union[Dict[str, Any], str, CacheReference]:
    """
    Get cryptocurrency global market data.

    Parameters:
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete market data (default)
      - return_type="preview": Return a text preview of the data
      - return_type="reference": Return a reference ID that can be used in other tool calls

    Examples:
    ```
    # Basic usage
    get_global_market_data()

    # Getting a reference to use in another call
    get_global_market_data(options={"return_type": "reference"})
    ```

    Returns global market statistics including market cap, volume, and market dominance.

    Returns:
    - With return_type="full": Complete market data (dictionary)
    - With return_type="preview": A string summary of the market data
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    logger.debug("Getting global market data")

    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    url = f"{COINGECKO_API_URL}/global"

    try:
        data = rate_limited_request(url)

        result = {
            "active_cryptocurrencies": data.get("data", {}).get(
                "active_cryptocurrencies"
            ),
            "markets": data.get("data", {}).get("markets"),
            "total_market_cap_usd": data.get("data", {})
            .get("total_market_cap", {})
            .get("usd"),
            "total_volume_usd": data.get("data", {}).get("total_volume", {}).get("usd"),
            "market_cap_percentage": data.get("data", {}).get("market_cap_percentage"),
            "market_cap_change_percentage_24h_usd": data.get("data", {}).get(
                "market_cap_change_percentage_24h_usd"
            ),
        }

        logger.info("Successfully retrieved global market data")
        return result

    except Exception as e:
        logger.error(f"Failed to get global market data: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get global market data: {str(e)}")


@mcp.tool(
    description="Get historical price data for a cryptocurrency over a specified time period."
)
@historical_cache.cached
def get_historical_price(
    request: HistoricalPriceRequest, options: Optional[ReturnTypeParam] = None
) -> Union[Dict[str, Any], str, CacheReference]:
    """
    Get historical price data for a cryptocurrency.

    Parameters:
    - request: The cryptocurrency and time period to get historical data for
      - coin_id: The ID of the coin on CoinGecko (e.g., 'bitcoin', 'ethereum') or a reference
      - days: Number of days of data to retrieve (1-365)
      - vs_currency: Currency to get prices in (e.g., 'usd', 'eur')
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete historical data (default)
      - return_type="preview": Return a text preview of the data
      - return_type="reference": Return a reference ID that can be used in other tool calls

    You can pass a CacheReference object instead of a literal value for the coin_id parameter
    to use a previously cached result.

    This data is ideal for visualization with the math_toolset's plot_data function.

    Examples:
    ```
    # Basic usage
    get_historical_price(request={"coin_id": "bitcoin", "days": 30, "vs_currency": "usd"})

    # Using a reference from another tool
    get_historical_price(request={"coin_id": <coin_reference>, "days": 7, "vs_currency": "usd"})

    # Getting a reference to use with plot_data in math_toolset
    historical_data_ref = get_historical_price(
        request={"coin_id": "ethereum", "days": 90, "vs_currency": "usd"},
        options={"return_type": "reference"}
    )

    # Then in math_toolset:
    plot_data(request={"data": historical_data_ref, "title": "ETH Price History", ...})
    ```

    Returns:
    - With return_type="full": Complete historical price data (dictionary)
    - With return_type="preview": A string summary of the historical data
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    # Process coin_id (handle references)
    coin_id = request.coin_id
    if isinstance(coin_id, CacheReference):
        resolved_value = historical_cache.resolve_reference(coin_id)
        if isinstance(resolved_value, dict) and "id" in resolved_value:
            # If the reference resolves to a coin info object, extract the ID
            coin_id = resolved_value["id"]
        elif isinstance(resolved_value, str):
            # If the reference resolves to a string, use it directly
            coin_id = resolved_value
        else:
            # Try to convert to string
            coin_id = str(resolved_value)

    logger.debug(
        f"Getting historical data for {coin_id} over {request.days} days in {request.vs_currency}"
    )

    # Limit days to reasonable range
    days = min(max(1, request.days), 365)

    url = f"{COINGECKO_API_URL}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": request.vs_currency,
        "days": days,
    }

    try:
        data = rate_limited_request(url, params)

        # Process the data into a more user-friendly format
        prices = [[timestamp, price] for timestamp, price in data.get("prices", [])]

        result = {
            "coin_id": coin_id,
            "days": days,
            "currency": request.vs_currency,
            "price_data": prices,
            "market_caps": data.get("market_caps", []),
            "total_volumes": data.get("total_volumes", []),
        }

        logger.info(f"Successfully retrieved historical data for {coin_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to get historical data: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get historical data: {str(e)}")


@mcp.tool(description="Search for cryptocurrencies by name or symbol.")
@search_cache.cached
def search_coins(
    request: SearchRequest, options: Optional[ReturnTypeParam] = None
) -> Union[Dict[str, Any], str, CacheReference]:
    """
    Search for cryptocurrencies by name or symbol.

    Parameters:
    - request: The search query
      - query: Search query string or a reference
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete search results (default)
      - return_type="preview": Return a text preview of the results
      - return_type="reference": Return a reference ID that can be used in other tool calls

    You can pass a CacheReference object instead of a literal value for the query parameter
    to use a previously cached result.

    Examples:
    ```
    # Basic usage
    search_coins(request={"query": "bitcoin"})

    # Using a reference from another tool
    search_coins(request={"query": <some_reference>})

    # Getting a reference to use in another call
    search_coins(
        request={"query": "defi"},
        options={"return_type": "reference"}
    )
    ```

    Returns:
    - With return_type="full": Complete search results (dictionary)
    - With return_type="preview": A string summary of the search results
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    # Process query (handle references)
    query = request.query
    if isinstance(query, CacheReference):
        resolved_value = search_cache.resolve_reference(query)
        if isinstance(resolved_value, dict) and "name" in resolved_value:
            # If the reference resolves to a coin info object, extract the name
            query = resolved_value["name"]
        elif isinstance(resolved_value, str):
            # If the reference resolves to a string, use it directly
            query = resolved_value
        else:
            # Try to convert to string
            query = str(resolved_value)

    logger.debug(f"Searching for coins with query: {query}")

    url = f"{COINGECKO_API_URL}/search"
    params = {"query": query}

    try:
        data = rate_limited_request(url, params)

        result = {
            "coins": [
                {
                    "id": coin["id"],
                    "name": coin["name"],
                    "symbol": coin["symbol"],
                    "market_cap_rank": coin.get("market_cap_rank"),
                }
                for coin in data.get("coins", [])[:20]  # Limit to top 20 results
            ]
        }

        logger.info(f"Found {len(result['coins'])} coins matching '{query}'")
        return result

    except Exception as e:
        logger.error(f"Failed to search coins: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to search coins: {str(e)}")


@mcp.tool(description="Get market data for top cryptocurrencies sorted by market cap.")
@market_cache.cached
def get_top_coins(
    request: TopCoinsRequest, options: Optional[ReturnTypeParam] = None
) -> Union[List[Dict[str, Any]], str, CacheReference]:
    """
    Get market data for top cryptocurrencies by market cap.

    Parameters:
    - request: The parameters for retrieving top coins
      - vs_currency: The currency to show prices in (e.g., 'usd', 'eur')
      - count: Number of top coins to return (1-250)
    - options: Optional parameter to control how results are returned:
      - return_type="full": Return the complete coin data (default)
      - return_type="preview": Return a text preview of the data
      - return_type="reference": Return a reference ID that can be used in other tool calls

    This data is ideal for visualization with the math_toolset's plot_data function.

    Examples:
    ```
    # Basic usage
    get_top_coins(request={"vs_currency": "usd", "count": 10})

    # Getting a reference to use with math_toolset for visualization
    top_coins_ref = get_top_coins(
        request={"vs_currency": "usd", "count": 5},
        options={"return_type": "reference"}
    )

    # Then in math_toolset:
    plot_data(
        request={
            "data": top_coins_ref,
            "x_field": "name",
            "y_field": "current_price",
            "title": "Top 5 Cryptocurrencies by Price",
            "x_label": "Coin",
            "y_label": "Price (USD)",
            "style": "bar"
        }
    )
    ```

    Returns:
    - With return_type="full": Complete market data for top coins (list of dictionaries)
    - With return_type="preview": A string summary of the top coins
    - With return_type="reference": A CacheReference object that can be used in other tool calls
    """
    logger.debug(f"Getting top {request.count} coins in {request.vs_currency}")

    # Handle return type option
    return_type = "full"
    if options:
        return_type = options.return_type

    # Limit count to reasonable range
    count = min(max(1, request.count), 250)

    url = f"{COINGECKO_API_URL}/coins/markets"
    params = {
        "vs_currency": request.vs_currency,
        "order": "market_cap_desc",
        "per_page": count,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h,7d,30d",
    }

    try:
        data = rate_limited_request(url, params)

        result = [
            {
                "id": coin.get("id"),
                "symbol": coin.get("symbol"),
                "name": coin.get("name"),
                "current_price": coin.get("current_price"),
                "market_cap": coin.get("market_cap"),
                "market_cap_rank": coin.get("market_cap_rank"),
                "total_volume": coin.get("total_volume"),
                "price_change_24h": coin.get("price_change_24h"),
                "price_change_percentage_24h": coin.get("price_change_percentage_24h"),
                "price_change_percentage_7d": coin.get(
                    "price_change_percentage_7d_in_currency"
                ),
                "price_change_percentage_30d": coin.get(
                    "price_change_percentage_30d_in_currency"
                ),
                "image": coin.get("image"),
            }
            for coin in data
        ]

        logger.info(f"Successfully retrieved data for top {len(result)} coins")
        return result

    except Exception as e:
        logger.error(f"Failed to get top coins: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get top coins: {str(e)}")


# ---- RESOURCES ----


@mcp.resource("crypto://api-info")
def get_api_info() -> Dict[str, Any]:
    """
    Provides information about the CoinGecko cryptocurrency API used by this toolset.
    """
    return {
        "name": "CoinGecko API",
        "base_url": COINGECKO_API_URL,
        "version": "v3",
        "documentation": "https://www.coingecko.com/en/api/documentation",
        "free_rate_limit": "10-50 calls/minute depending on endpoint",
        "tools_available": [
            "get_coin_info - Detailed data about a specific coin",
            "get_coin_price - Current prices for multiple coins",
            "get_trending_coins - List of trending coins in last 24h",
            "get_global_market_data - Overall crypto market statistics",
            "get_historical_price - Price history for a coin",
            "search_coins - Find coins by name or symbol",
            "get_top_coins - List top coins by market cap",
        ],
        "reference_system": "All tools support the reference system for chaining operations and visualization",
    }


@mcp.resource("crypto://reference-usage-guide")
def get_reference_usage_guide() -> str:
    """
    Provides a guide on how to use the reference system with the Crypto Toolset,
    including examples of integrating with the Math Toolset for visualization.
    """
    return """
    # Crypto Toolset Reference System Guide

    This toolset supports a powerful reference system that allows you to:

    1. Chain cryptocurrency operations together
    2. Use results from one crypto tool in another
    3. Pass crypto data to other toolsets (like Math Toolset) for visualization

    ## How to use references

    ### 1. Getting a reference

    Add the `return_type="reference"` parameter to any tool call:

    ```
    # Get Bitcoin info and store as reference
    bitcoin_ref = get_coin_info(
        request={"coin_id": "bitcoin"},
        options={"return_type": "reference"}
    )
    ```

    ### 2. Using a reference in another crypto tool

    Simply pass the reference object directly:

    ```
    # Get historical price using the bitcoin reference
    bitcoin_history = get_historical_price(
        request={"coin_id": bitcoin_ref, "days": 30, "vs_currency": "usd"}
    )
    ```

    ### 3. Creating visualizations with Math Toolset

    Pass crypto references to the Math Toolset for visualization:

    ```
    # Get historical price data as reference
    history_ref = get_historical_price(
        request={"coin_id": "bitcoin", "days": 30, "vs_currency": "usd"},
        options={"return_type": "reference"}
    )

    # Use Math Toolset's plot_data to visualize
    plot_data(
        request={
            "data": history_ref,
            "title": "Bitcoin 30-Day Price History",
            "x_label": "Date",
            "y_label": "Price (USD)",
            "style": "line",
            "color": "orange"
        }
    )
    ```

    ### 4. Previewing data

    Get a summary of data without retrieving the full result:

    ```
    preview = get_top_coins(
        request={"vs_currency": "usd", "count": 10},
        options={"return_type": "preview"}
    )
    ```

    ## Example workflows

    ### Trend discovery workflow

    ```
    # Get trending coins as reference
    trending_ref = get_trending_coins(options={"return_type": "reference"})

    # Get detailed info about the first trending coin
    # The reference system will automatically extract the first coin ID
    first_trending_info = get_coin_info(
        request={"coin_id": trending_ref}
    )
    ```

    ### Price comparison visualization

    ```
    # Get top 5 coins by market cap as reference
    top_coins_ref = get_top_coins(
        request={"vs_currency": "usd", "count": 5},
        options={"return_type": "reference"}
    )

    # Use Math Toolset to create a bar chart comparing prices
    plot_data(
        request={
            "data": top_coins_ref,
            "x_field": "name",
            "y_field": "current_price",
            "title": "Top Cryptocurrency Prices",
            "x_label": "Cryptocurrency",
            "y_label": "Price (USD)",
            "style": "bar",
            "color": "green"
        }
    )
    ```

    ### Historical price analysis

    ```
    # Get Bitcoin historical data
    btc_history_ref = get_historical_price(
        request={"coin_id": "bitcoin", "days": 30, "vs_currency": "usd"},
        options={"return_type": "reference"}
    )

    # Get Ethereum historical data
    eth_history_ref = get_historical_price(
        request={"coin_id": "ethereum", "days": 30, "vs_currency": "usd"},
        options={"return_type": "reference"}
    )

    # Compare both in a single visualization using Math Toolset
    # (This would require custom logic in plot_data to handle multiple datasets)
    ```
    """


if __name__ == "__main__":
    logger.info("Starting Crypto API server")
    try:
        mcp.run(transport="stdio")
    finally:
        # Flush deterministic caches on shutdown
        historical_cache.flush()
        search_cache.flush()
