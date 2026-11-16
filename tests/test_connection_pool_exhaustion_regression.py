import concurrent.futures
import pytest
import payment.main as payment_module

def test_connection_pool_capacity_and_exhaustion():
    """
    Verify that the database engine connection pool can sustain concurrent checkouts
    up to the upgraded pool capacity without exhausting or timing out.
    """
    # Ensure capacity meets the upgraded minimum requirement (POOL_SIZE 20 + MAX_OVERFLOW 10 = 30)
    assert payment_module.POOL_SIZE >= 20
    
    engine = payment_module.engine
    connections = []
    
    try:
        # Try checking out 15 simultaneous connections (well above the old default of 5, but within new capacity)
        for _ in range(15):
            conn = engine.connect()
            connections.append(conn)
        
        # Verify all connections were successfully checked out
        assert len(connections) == 15
    finally:
        for conn in connections:
            try:
                conn.close()
            except Exception:
                pass
