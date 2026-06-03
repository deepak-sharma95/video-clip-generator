"""
ClipGenius - Desktop GUI
========================
Launches the ClipGenius Web App in a native desktop window using pywebview.
"""

import webview
import time
import requests

def wait_for_server():
    """Wait for the Flask API to become available."""
    print("Waiting for server to start...")
    for _ in range(30):
        try:
            response = requests.get("http://localhost:5000/")
            if response.status_code == 200:
                print("Server is ready!")
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    print("Failed to connect to server.")
    return False

if __name__ == "__main__":
    if wait_for_server():
        print("Launching ClipGenius window...")
        webview.create_window(
            title="ClipGenius | Viral YouTube Clip Extractor",
            url="http://localhost:5000/",
            width=1000,
            height=700,
            resizable=True,
            min_size=(800, 600),
            background_color="#0f1115",
        )
        webview.start()
