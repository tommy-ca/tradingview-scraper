import asyncio
import logging
import os

from tradingview_scraper.symbols.stream.streamer_async import AsyncStreamer

# Set your JWT token here or via environment variable
JWT_TOKEN = os.getenv("TRADINGVIEW_JWT_TOKEN", "unauthorized_user_token")


async def main():
    logging.basicConfig(level=logging.INFO)

    # 1. Initialize AsyncStreamer
    streamer = AsyncStreamer(websocket_jwt_token=JWT_TOKEN)

    try:
        # 2. Start streaming
        # This returns an async generator
        print("Connecting to TradingView WebSocket...")
        data_gen = await streamer.stream(exchange="BINANCE", symbol="BTCUSDT", timeframe="1m", numb_price_candles=5)

        print("Successfully subscribed! Listening for data...")

        # 3. Consume data using 'async for'
        packet_count = 0
        async for pkt in data_gen:
            packet_count += 1
            method = pkt.get("m")

            if method == "timescale_update":
                print(f"[{packet_count}] Received OHLC Update")
            elif method == "du":
                print(f"[{packet_count}] Received Study Update (Indicator)")
            else:
                print(f"[{packet_count}] Received Message: {method}")

            # Stop after 10 packets for this example
            if packet_count >= 10:
                print("Reached example limit. Stopping.")
                break

    except Exception as e:
        print(f"Error during streaming: {e}")
    finally:
        # 4. Clean up
        print("Closing streamer...")
        await streamer.close()


if __name__ == "__main__":
    asyncio.run(main())
