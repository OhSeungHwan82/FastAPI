from pydantic import BaseModel
from typing import List
from fastapi import UploadFile
from typing import Optional

class CreateRequest(BaseModel):
    info_request_pk:int

class UpdateRequest(BaseModel):
	requestSql: Optional[str] = None
	is_valid:str
	file: Optional[UploadFile] = None
class CreateReviveRequest(BaseModel):
    ld_pk:int    
