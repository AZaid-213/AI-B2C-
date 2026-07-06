from app.main import app

"""Launcher module to expose the ASGI app at the project root.

Uvicorn can be run with:

    uvicorn main:app --reload

"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
