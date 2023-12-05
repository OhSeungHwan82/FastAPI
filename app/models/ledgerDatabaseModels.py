from pydantic import BaseModel
from typing import List

class CreateRequest(BaseModel):
    info_request_pk:int

class UpdateRequest(BaseModel):
	requestSql:str

class CreateReviveRequest(BaseModel):
    ld_pk:int    
