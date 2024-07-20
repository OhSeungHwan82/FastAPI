from pydantic import BaseModel
from typing import List
from fastapi import UploadFile
from typing import Optional

class KeyValueItem(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
class CreateJobTempleate(BaseModel):
    gubun:str
    name:str
    status:str
    description:Optional[str] = None
    executionscript:str
    buildschedule:Optional[str] = None
    params:Optional[List[KeyValueItem]] = None

class ExecJobTempleate(BaseModel):
    params:Optional[List[KeyValueItem]] = None

class UpdateJobTempleate(BaseModel):
    status:str
    description:Optional[str] = None

class CreateJobRequest(BaseModel):
    jt_pk:int


