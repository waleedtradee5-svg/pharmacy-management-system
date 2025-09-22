import streamlit.web.cli as stcli
import sys
import os

if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        os.path.join(os.path.dirname(__file__), "app.py"),
        "--global.developmentMode=false"
    ]
    stcli.main()