from sqlalchemy import text


def test_db_connection(test_db):
    result = test_db.execute(text("SELECT 1")).scalar()
    assert result == 1
