from pydantic import BaseModel

class MovieOut(BaseModel):
    id: int
    title: str
    genres: str
