"""Price tracking system for Pokemon cards with daily snapshots"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, select
from tqdm import tqdm
import statistics

from .models import (
    PokemonCard, CardVariation, PriceSnapshot,
    get_session, DatabaseConfig
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PriceTracker:
    """Track Pokemon card prices from TCGPlayer API"""
    
    def __init__(self, session: Session, api_key: Optional[str] = None):
        self.session = session
        self.api_key = api_key
        self.tcgplayer_base = "https://api.tcgplayer.com/v1.39.0"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Pokemon-Price-Tracker/1.0"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def track_all_prices(self, conditions: List[str] = None):
        """Track prices for all cards in database"""
        if conditions is None:
            conditions = ["NM", "LP"]  # Near Mint and Lightly Played
        
        logger.info(f"Starting price tracking for conditions: {conditions}")
        
        # Get all cards with TCGPlayer IDs
        cards = self.session.query(PokemonCard).filter(
            PokemonCard.tcgplayer_id.isnot(None)
        ).all()
        
        logger.info(f"Found {len(cards)} cards to track")
        
        # Process in batches to avoid overwhelming the API
        batch_size = 100
        for i in range(0, len(cards), batch_size):
            batch = cards[i:i + batch_size]
            await self._process_card_batch(batch, conditions)
            await asyncio.sleep(1)  # Rate limiting
        
        self.session.commit()
        logger.info("Price tracking completed")
    
    async def _process_card_batch(self, cards: List[PokemonCard], conditions: List[str]):
        """Process a batch of cards"""
        tasks = []
        
        async with aiohttp.ClientSession() as session:
            for card in cards:
                for condition in conditions:
                    task = self._fetch_and_save_price(session, card, condition)
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error fetching price: {result}")
    
    async def _fetch_and_save_price(self, session: aiohttp.ClientSession, 
                                   card: PokemonCard, condition: str):
        """Fetch and save price for a single card"""
        try:
            # Fetch price data from TCGPlayer
            prices = await self._fetch_tcgplayer_prices(session, card.tcgplayer_id)
            
            if not prices:
                return
            
            # Process each variation
            for variation in card.variations:
                price_data = self._extract_variation_price(prices, variation, condition)
                
                if price_data:
                    # Create price snapshot
                    snapshot = PriceSnapshot(
                        card_id=card.id,
                        variation_id=variation.id,
                        timestamp=datetime.utcnow(),
                        prices=price_data,
                        source="tcgplayer",
                        condition=condition,
                        currency="USD",
                        volume=price_data.get("volume"),
                        listings_count=price_data.get("listings_count")
                    )
                    
                    self.session.add(snapshot)
        
        except Exception as e:
            logger.error(f"Error tracking price for {card.name}: {e}")
    
    async def _fetch_tcgplayer_prices(self, session: aiohttp.ClientSession, 
                                    product_id: str) -> Optional[Dict[str, Any]]:
        """Fetch current prices from TCGPlayer"""
        # This is a placeholder - actual implementation would use TCGPlayer API
        # For now, simulate with mock data
        
        # In production, this would be:
        # url = f"{self.tcgplayer_base}/pricing/product/{product_id}"
        # async with session.get(url, headers=self.headers) as response:
        #     return await response.json()
        
        # Mock data for demonstration
        return {
            "success": True,
            "results": [
                {
                    "productId": product_id,
                    "lowPrice": 8.00,
                    "midPrice": 10.00,
                    "highPrice": 15.00,
                    "marketPrice": 10.50,
                    "directLowPrice": None,
                    "subTypeName": "Normal"
                }
            ]
        }
    
    def _extract_variation_price(self, price_data: Dict[str, Any], 
                               variation: CardVariation, 
                               condition: str) -> Optional[Dict[str, Any]]:
        """Extract price for specific variation"""
        # Match variation to price data
        # This would need proper mapping based on TCGPlayer's variation naming
        
        for result in price_data.get("results", []):
            # Simple matching logic - would be more complex in production
            if self._matches_variation(result, variation):
                return {
                    "market": result.get("marketPrice"),
                    "low": result.get("lowPrice"),
                    "mid": result.get("midPrice"),
                    "high": result.get("highPrice"),
                    "direct_low": result.get("directLowPrice"),
                    "volume": result.get("volume", 0),
                    "listings_count": result.get("listingsCount", 0)
                }
        
        return None
    
    def _matches_variation(self, price_result: Dict[str, Any], 
                         variation: CardVariation) -> bool:
        """Check if price result matches variation"""
        subtype = price_result.get("subTypeName", "").lower()
        
        if variation.is_first_edition and "1st edition" not in subtype:
            return False
        
        if variation.is_reverse_holo and "reverse" not in subtype:
            return False
        
        if not variation.is_reverse_holo and not variation.is_first_edition:
            return subtype == "normal" or subtype == "holofoil"
        
        return True


class PriceAnalyzer:
    """Analyze price trends and provide insights"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_price_trend(self, card_id: str, variation_id: Optional[str] = None,
                       days: int = 30, condition: str = "NM") -> Dict[str, Any]:
        """Get price trend for a card over specified days"""
        since = datetime.utcnow() - timedelta(days=days)
        
        query = self.session.query(PriceSnapshot).filter(
            PriceSnapshot.card_id == card_id,
            PriceSnapshot.timestamp >= since,
            PriceSnapshot.condition == condition
        )
        
        if variation_id:
            query = query.filter(PriceSnapshot.variation_id == variation_id)
        
        snapshots = query.order_by(PriceSnapshot.timestamp).all()
        
        if not snapshots:
            return {"error": "No price data available"}
        
        # Extract price series
        timestamps = []
        market_prices = []
        low_prices = []
        high_prices = []
        
        for snapshot in snapshots:
            timestamps.append(snapshot.timestamp)
            prices = snapshot.prices or {}
            market_prices.append(prices.get("market", 0))
            low_prices.append(prices.get("low", 0))
            high_prices.append(prices.get("high", 0))
        
        # Calculate trends
        return {
            "card_id": card_id,
            "variation_id": variation_id,
            "condition": condition,
            "period_days": days,
            "data_points": len(snapshots),
            "timestamps": timestamps,
            "market_prices": market_prices,
            "low_prices": low_prices,
            "high_prices": high_prices,
            "trends": self._calculate_trends(market_prices, timestamps),
            "statistics": self._calculate_statistics(market_prices)
        }
    
    def _calculate_trends(self, prices: List[float], 
                         timestamps: List[datetime]) -> Dict[str, Any]:
        """Calculate price trends"""
        if len(prices) < 2:
            return {"trend": "insufficient_data"}
        
        # Remove zeros
        valid_prices = [(p, t) for p, t in zip(prices, timestamps) if p > 0]
        
        if not valid_prices:
            return {"trend": "no_valid_prices"}
        
        prices, timestamps = zip(*valid_prices)
        
        # Calculate percentage change
        first_price = prices[0]
        last_price = prices[-1]
        change_percent = ((last_price - first_price) / first_price) * 100
        
        # Determine trend direction
        if change_percent > 5:
            trend = "increasing"
        elif change_percent < -5:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Find peak and trough
        peak_price = max(prices)
        peak_date = timestamps[prices.index(peak_price)]
        
        trough_price = min(prices)
        trough_date = timestamps[prices.index(trough_price)]
        
        return {
            "trend": trend,
            "change_percent": round(change_percent, 2),
            "first_price": first_price,
            "last_price": last_price,
            "peak": {
                "price": peak_price,
                "date": peak_date.isoformat()
            },
            "trough": {
                "price": trough_price,
                "date": trough_date.isoformat()
            }
        }
    
    def _calculate_statistics(self, prices: List[float]) -> Dict[str, Any]:
        """Calculate price statistics"""
        valid_prices = [p for p in prices if p > 0]
        
        if not valid_prices:
            return {"error": "No valid prices"}
        
        return {
            "mean": round(statistics.mean(valid_prices), 2),
            "median": round(statistics.median(valid_prices), 2),
            "stdev": round(statistics.stdev(valid_prices), 2) if len(valid_prices) > 1 else 0,
            "min": min(valid_prices),
            "max": max(valid_prices),
            "current": valid_prices[-1] if valid_prices else None
        }
    
    def get_top_movers(self, days: int = 7, limit: int = 20) -> Dict[str, List[Dict]]:
        """Get top gaining and losing cards"""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get cards with price data in the period
        subquery = (
            select(
                PriceSnapshot.card_id,
                func.min(PriceSnapshot.timestamp).label('first_date'),
                func.max(PriceSnapshot.timestamp).label('last_date')
            )
            .where(
                and_(
                    PriceSnapshot.timestamp >= since,
                    PriceSnapshot.condition == 'NM'
                )
            )
            .group_by(PriceSnapshot.card_id)
            .subquery()
        )
        
        # Get first and last prices
        results = []
        
        cards = self.session.query(PokemonCard).join(
            subquery, PokemonCard.id == subquery.c.card_id
        ).all()
        
        for card in cards:
            trend = self.get_price_trend(str(card.id), days=days)
            
            if trend.get("trends") and trend["trends"].get("change_percent"):
                results.append({
                    "card": card,
                    "change_percent": trend["trends"]["change_percent"],
                    "first_price": trend["trends"]["first_price"],
                    "last_price": trend["trends"]["last_price"]
                })
        
        # Sort by change percentage
        results.sort(key=lambda x: x["change_percent"], reverse=True)
        
        return {
            "gainers": results[:limit],
            "losers": results[-limit:] if len(results) > limit else []
        }
    
    def get_price_alerts(self, threshold_percent: float = 10) -> List[Dict[str, Any]]:
        """Get cards with significant price changes in last 24 hours"""
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        alerts = []
        
        # Get cards with recent price updates
        recent_cards = self.session.query(PokemonCard).join(PriceSnapshot).filter(
            PriceSnapshot.timestamp >= yesterday
        ).distinct().all()
        
        for card in recent_cards:
            trend = self.get_price_trend(str(card.id), days=1)
            
            if trend.get("trends") and abs(trend["trends"].get("change_percent", 0)) >= threshold_percent:
                alerts.append({
                    "card_name": card.name,
                    "set_name": card.set.name,
                    "change_percent": trend["trends"]["change_percent"],
                    "current_price": trend["statistics"]["current"],
                    "alert_type": "price_increase" if trend["trends"]["change_percent"] > 0 else "price_decrease"
                })
        
        return alerts


class PriceScheduler:
    """Schedule daily price tracking jobs"""
    
    def __init__(self, connection_string: str, api_key: Optional[str] = None):
        self.connection_string = connection_string
        self.api_key = api_key
    
    async def run_daily_tracking(self):
        """Run daily price tracking"""
        engine = DatabaseConfig.get_engine(self.connection_string)
        session = get_session(engine)
        
        try:
            tracker = PriceTracker(session, self.api_key)
            await tracker.track_all_prices()
            
            # Generate alerts
            analyzer = PriceAnalyzer(session)
            alerts = analyzer.get_price_alerts()
            
            if alerts:
                logger.info(f"Price alerts: {len(alerts)} cards with significant changes")
                for alert in alerts[:5]:  # Log top 5
                    logger.info(f"  {alert['card_name']}: {alert['change_percent']:+.1f}%")
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Error in daily tracking: {e}")
            session.rollback()
            raise
        finally:
            session.close()
    
    async def run_forever(self):
        """Run price tracking on schedule"""
        while True:
            try:
                # Run at 2 AM UTC daily
                now = datetime.utcnow()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"Next price tracking in {wait_seconds/3600:.1f} hours")
                
                await asyncio.sleep(wait_seconds)
                await self.run_daily_tracking()
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(3600)  # Wait an hour on error


async def main():
    """Test price tracking"""
    connection_string = DatabaseConfig.get_connection_string(
        host='localhost',
        database='pokemon_tcg',
        username='postgres',
        password='your_password'
    )
    
    engine = DatabaseConfig.get_engine(connection_string)
    session = get_session(engine)
    
    try:
        # Test tracking
        tracker = PriceTracker(session)
        
        # Track a few cards for testing
        test_cards = session.query(PokemonCard).limit(5).all()
        for card in test_cards:
            logger.info(f"Tracking prices for: {card.name}")
        
        # Test analysis
        analyzer = PriceAnalyzer(session)
        
        if test_cards:
            trend = analyzer.get_price_trend(str(test_cards[0].id))
            logger.info(f"Price trend for {test_cards[0].name}: {trend}")
        
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())