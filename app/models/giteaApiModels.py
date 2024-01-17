from pydantic import BaseModel, Field
from typing import List

class PmItem(BaseModel):
	info_request_pk: int = Field(title='정보처리요청게시판 PK')

class Item(BaseModel):
	webhook_url: str = Field(title='네이트온 웹훅URL')
	content: str = Field(title='웹훅에 보낼 메시지')

class IrItem(BaseModel):
	jubsu_no: str = Field(title='정보처리요청게시판 접수번호')
	hash_code: str = Field(title='GIT HASH CODE')
	gubun: str = Field(title='테스트,운영')
	upmu_gubun: str = Field(title='Client, Server')    
