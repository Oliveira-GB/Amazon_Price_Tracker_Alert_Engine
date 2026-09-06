



class TestDecisionWorker:
    def test_build_message_with_target(self):
        from workers.decision.consumer import DecisionWorker

        worker = DecisionWorker()
        msg = worker._build_message(
            asin="B08ABC1234",
            current_price=299.99,
            target_price=350.00,
            title="Test Product",
        )
        assert "299.99" in msg
        assert "350.00" in msg

    def test_build_message_all_time_low(self):
        from workers.decision.consumer import DecisionWorker

        worker = DecisionWorker()
        msg = worker._build_message(
            asin="B08ABC1234",
            current_price=199.99,
            target_price=None,
            title="Test Product",
        )
        assert "199.99" in msg
        assert "histórico" in msg.lower()

    def test_build_message_truncates_title(self):
        from workers.decision.consumer import DecisionWorker

        worker = DecisionWorker()
        long_title = "A" * 100
        msg = worker._build_message(
            asin="B08ABC1234",
            current_price=299.99,
            target_price=350.00,
            title=long_title,
        )
        assert "..." in msg
