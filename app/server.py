from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langserve import add_routes
from mangum import Mangum

app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="Spin up a simple api server using Langchain's Runnable interfaces",
)


@app.get("/", status_code=200)
async def return_ok():
    return {"status": "ok"}


add_routes(
    app,
    ChatOpenAI(),
    path="/openai",
)

handler = Mangum(app)