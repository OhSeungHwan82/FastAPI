from pydantic import BaseModel
from typing import List
from fastapi import UploadFile
from typing import Optional

class CreateJobTempleate(BaseModel):
    gubun:str
    name:str
    status:str
    description:Optional[str] = None
    executionscript:str

class UpdateJobTempleate(BaseModel):
    gubun:str
    name:str
    status:str
    description:Optional[str] = None
    executionscript:str
    param1:Optional[str] = None
    param2:Optional[str] = None
    param3:Optional[str] = None

class CreateJobRequest(BaseModel):
    jt_pk:int
