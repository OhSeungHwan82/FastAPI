# -*- coding: utf-8 -*-
import requests
import sys
import time
from fastapi import APIRouter, FastAPI, Body, Query
from app.database.orcl import DbLink  
from pydantic import BaseModel
from pydantic import Field
from typing import Optional
 
router = APIRouter(
    prefix="/api/devSample",
)
class Item(BaseModel):
	webhook_url: str = Field(title='네이트온 웹훅URL')
	content: str = Field(title='웹훅에 보낼 메시지')

@router.get("/items", name="GET 샘플", description="GET 샘플의 파라미터 세팅방법")
def getSample1(
	item_id1: int = Query(None,description="item_id1 타입은 int, 기본값 생략"),
	item_id2: int = Query(0,description="item_id2 타입은 int, 기본값 0"),
	item_id3: str = Query("문자열 default",description="item_id3 타입은 str, 기본값 문자열 default"),
	item_id4: bool = Query(True,description="item_id4 타입은 bool, 기본값 True"),
	item_id5: float  = Query(99.99,description="item_id5 타입은 float , 기본값 실수 99.99"),
	item_id6: str = Query(...,description="item_id6 타입은 str, 순서가 있는 열거형", enum=["enum1","enum2","enum3"]),
):
	results = {"item_id1": item_id1, "item": "item"}
	return results

@router.get("/items/{item_id}", name="두번째 GET 샘플", description="두번째 GET 샘플의 파라미터 세팅방법")
def getSample2(item_id:int):
	if item_id == 1:
		return "1"
	else:
		return "100"

class Item1(BaseModel):
	name: str
	description: Optional[str] = None
	price: float
	tax: Optional[float] = None


@router.post("/items", name="POST 샘플", description="POST 샘플의 파라미터 세팅방법")
def postSample(
	item: Item1 = Body(
        ...,
		description="An example item",
        example={
            "name": "Foo",
            "description": "A very nice Item",
            "price": 35.4,
            "tax": 3.2,
        },
	),
):
	results = item.name
	return results

item_datas = {
    1:{
        "user_id":1,
        "user_name":"오승환",
    },
    2:{
        "user_id":2,
        "user_name":"박경수",
    },
    3:{
        "user_id":3,
        "user_name":"서정배",
    }
}
@router.patch("/items/{item_id}", name="PATCH 샘플", description="PATCH 샘플의 파라미터 세팅방법")
def update_todo_handler(
    item_id:int,
    user_name:str = Body()
    ):
    item_data = item_datas.get(item_id)
    if item_data:
        item_data["user_name"] = user_name
        return item_data
    return {}


@router.delete("/items/{item_id}", name="DELETE 샘플", description="DELETE 샘플의 파라미터 세팅방법")
def update_todo_handler(
    item_id:int,
    ):
    item_datas.pop(item_id)
    return item_datas
