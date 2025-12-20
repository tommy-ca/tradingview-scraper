from unittest.mock import patch

from websocket import WebSocketConnectionClosedException

from tradingview_scraper.symbols.stream import Streamer


def test_streamer_reconnects_on_connection_closed():
    """
    Test that Streamer attempts to reconnect when WebSocketConnectionClosedException occurs.
    """
    with patch("tradingview_scraper.symbols.stream.streamer.StreamHandler") as MockStreamHandler:
        mock_handler = MockStreamHandler.return_value
        mock_ws = mock_handler.ws

        # Simulate data, then connection loss, then more data
        mock_ws.recv.side_effect = [
            '~m~20~m~{"m":"timescale_update","p":[{},{"sds_1":{"s":[{"i":0,"v":[1600000000,1,2,3,4,10]}]}}]}',
            WebSocketConnectionClosedException("Connection lost"),
            '~m~20~m~{"m":"timescale_update","p":[{},{"sds_1":{"s":[{"i":1,"v":[1600000060,2,3,4,5,20]}]}}]}',
        ]

        streamer = Streamer(export_result=False)
        # Mock sleep to avoid actual delay in tests
        with patch("tradingview_scraper.symbols.stream.streamer.sleep"):
            # We use get_data() directly to test the loop
            data_gen = streamer.get_data()

            # First packet
            pkt1 = next(data_gen)
            assert pkt1["m"] == "timescale_update"

            # The next() call should encounter the exception,
            # trigger reconnect (re-init StreamHandler), and then yield the next packet
            pkt2 = next(data_gen)
            assert pkt2["m"] == "timescale_update"
            assert pkt2["p"][1]["sds_1"]["s"][0]["i"] == 1

            # Verify MockStreamHandler was called twice (initial + reconnect)
            assert MockStreamHandler.call_count == 2
