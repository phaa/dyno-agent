import streamlit as st
import httpx

st.title("Dyno Agent UI")

if st.button("List Vehicles"):
    with httpx.Client() as client:
        response = client.get("http://fastapi:8000/vehicles")
        if response.status_code == 200:
            st.write(response.json())
        else:
            st.error("Failed to get response from FastAPI")