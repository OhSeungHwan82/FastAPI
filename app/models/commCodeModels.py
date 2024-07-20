from pydantic import BaseModel
from typing import List
from fastapi import UploadFile
from typing import Optional

class CreateClcode(BaseModel):
    cl_code:int
    cl_name:str
    cl_description: Optional[str] = None
class UpdateClcode(BaseModel):
	cl_name: str 
	cl_description: Optional[str] = None
class CreateCode(BaseModel):
    cl_code:int
    code_id:str
    code_nm:str
    cl_description: Optional[str] = None
class UpdateCode(BaseModel):
	code_nm: str 
	code_description: Optional[str] = None
