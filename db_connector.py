import streamlit as st
import mysql.connector
import pandas as pd
from contextlib import contextmanager
import json

# Database ke credentials ke liye Streamlit ke secrets istemal karein
DB_CONFIG = {
    "host": st.secrets.get("db_host", "localhost"),
    "user": st.secrets.get("db_user", "root"),
    "password": st.secrets.get("db_password", "root"),
    "database": st.secrets.get("db_name", "pharmacy_erp"),
}


@contextmanager
def get_db_connection():
    """Database connections ke liye context manager."""
    conn = None  # conn ko pehle se None set karein
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        yield conn
    except mysql.connector.Error as err:
        st.error(f"Database Connection Error: {err}")
        yield None
    finally:
        if conn and conn.is_connected():
            conn.close()


def fetch_data(query, params=None):
    """Data fetch karke usse Pandas DataFrame mein return karta hai."""
    with get_db_connection() as conn:
        if conn:
            try:
                return pd.read_sql(query, conn, params=params)
            except Exception as e:
                st.error(f"Query Error: {e}")
                return pd.DataFrame()
    return pd.DataFrame()


def execute_query(query, params=None, return_last_id=False):
    """
    Ek single non-SELECT query (INSERT, UPDATE, DELETE) execute karta hai.
    Agar return_last_id True hai, to last inserted ID return karta hai.
    """
    with get_db_connection() as conn:
        if conn:
            cursor = conn.cursor()
            try:
                # JSON data ko sahi se handle karein
                formatted_params = None
                if params:
                    formatted_params = tuple(
                        json.dumps(p) if isinstance(p, (dict, list)) else p
                        for p in params
                    )

                cursor.execute(query, formatted_params or ())
                conn.commit()

                # UPDATE: Agar last ID chahiye to woh return karein
                if return_last_id:
                    last_id = cursor.lastrowid
                    return True, last_id

                return True, None
            except mysql.connector.Error as err:
                st.error(f"Execution Error: {err}")
                conn.rollback()
                return False, None
            finally:
                cursor.close()
    return False, None


def execute_transaction(queries_with_params):
    """
    Queries ki list ko ek single atomic transaction ke taur par execute karta hai.
    List mein har item ek tuple hona chahiye: (query, params_tuple).
    """
    with get_db_connection() as conn:
        if conn:
            cursor = conn.cursor()
            try:
                conn.start_transaction()
                for query, params in queries_with_params:
                    formatted_params = None
                    if params:
                        formatted_params = tuple(
                            json.dumps(p) if isinstance(p, (dict, list)) else p
                            for p in params
                        )
                    cursor.execute(query, formatted_params or ())

                # FIX: Commit loop ke bahar hona chahiye, taake poori transaction ek saath ho
                conn.commit()
                return True
            except mysql.connector.Error as err:
                st.error(f"Transaction Failed: {err}")
                conn.rollback()
                return False
            finally:
                cursor.close()
    return False
