import streamlit as st
import httpx

st.title("Dyno Agent UI")

if st.button("Say Hello"):
    with httpx.Client() as client:
        response = client.get("http://fastapi:8000/hello")
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error("Failed to get response from FastAPI")