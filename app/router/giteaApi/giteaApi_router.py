# -*- coding: utf-8 -*-
import requests
import sys
import time
from fastapi import APIRouter
from app.database.orcl import DbLink  
from pydantic import BaseModel
from pydantic import Field

 
router = APIRouter(
    prefix="/api/giteaApi",
)
class Item(BaseModel):
	webhook_url: str = Field(title='네이트온 웹훅URL')
	content: str = Field(title='웹훅에 보낼 메시지')

@router.post("/webhook", name="네이트온 웹훅", description="네이트온의 웹훅URL과 메시지를 받아 팀룸에 메시지 보내기")
def webhookSend(item:Item):
	dataInfo = {'content':item.content}
	URL = item.webhook_url
	response = requests.post(URL, data=dataInfo)

@router.post("/test", name="네이트온 웹훅", description="네이트온의 웹훅URL과 메시지를 받아 팀룸에 메시지 보내기")
def webhookSendtest():
	jubsu_no ='vvv'
	login_user = 'ww'
	content = f"""□  PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정상 접수 되었습니다."""
	dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
	URL = 'http://10.16.16.160/api/giteaApi/webhook'
	response = requests.post(URL, json=dataInfo)
	return

@router.post("/prlist")
def pullrequestlist(payload: dict):
	# 1 : 요청등록
	# 2 : 접수
	# 3 : 접수확정
	# 12: 개발접수
	# 4 : 개발승인
	# 5 : 진행
	# 9 : 테스트
	# 13: 테스트완료
	# 6 : 인수승인
	# 10: 이행승인
	# 11: 이행완료
	# 7 : 완료
	# 99: 반려
	repository_dict = {'test_iims_plus','□  PR 요청  □\n'}
	print(payload)
	
	jubsu_no =""
	login_user = ""
	pr_index = ""
	pr_msg = ""
	pr_url = ""
	if payload.get('action') and payload.get('pull_request'):
		value = payload['action']
		if 'opened' in value:
			if type(payload['pull_request']) is dict:
				pr_dict = payload['pull_request']
				print(pr_dict)
				if pr_dict.get("title") and pr_dict.get("user"):
					jubsu_no = pr_dict['title']
					pr_index = pr_dict['number']
					pr_msg = pr_dict['body']
					pr_url = pr_dict['url']
					#print(jubsu_no)
					if type(pr_dict['user']) is dict:
						user_dict = pr_dict['user']
						if user_dict.get("login"):
							#login_user = user_dict['login']
							login_user = user_dict['full_name']

			if not jubsu_no.isdigit() or len(jubsu_no)!=11:
				content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청제목은 접수번호만 가능합니다. \n             다시 요청 하시기 바랍니다."""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return

			db = DbLink()

			try:
				#jubsu_no =0
				qry = """select count(*) cnt from info_request where jubsu_no = :jubsu_no and use_yb ='1'
			"""
				bind_arr = {"jubsu_no":jubsu_no}
				db.execute(qry , bind_arr)
				fields = db.get_field_names()
				datas = db.get_datas()
				total_records = ''.join(map(str,datas[0]))
				print(type(total_records))
				total_rec = int(total_records)
				if total_rec==0:
					content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정보처리요청게시판에서 조회 할 수 없는 접수번호입니다. \n             다시 요청 하시기 바랍니다."""
					dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
					URL = 'http://10.16.16.160/api/giteaApi/webhook'
					response = requests.post(URL, json=dataInfo)
					db.close()
					return
				else:
					qry = """select count(*) cnt from info_request where jubsu_no = :jubsu_no and use_yb ='1' and status_cd in ('1','2','3','12','4','5','9')
			"""
				bind_arr = {"jubsu_no":jubsu_no}
				db.execute(qry , bind_arr)
				fields = db.get_field_names()
				datas = db.get_datas()
				req_exist = ''.join(map(str,datas[0]))
				#print(type(req_exist))
				req_exist_int = int(req_exist)
				if req_exist_int==0:
					content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정보처리요청게시판의 상태가 테스트완료 이후는 더이상 요청 할 수 없습니다. \n             새로운 접수번호로 요청 하시기 바랍니다."""
					dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
					URL = 'http://10.16.16.160/api/giteaApi/webhook'
					response = requests.post(URL, json=dataInfo)
					db.close()
					return
			except Exception as e:
				print("예외발생",e)
				content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 예외발생{e}"""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				#dataInfo = {'content':e,'jubsu_no':jubsu_no,'login_user':login_user,'status':'pr'}
				#URL = 'http://air.incar.co.kr/Support/Test/Test3'
				#response = requests.post(URL, data=dataInfo)
				db.close()
				return
			db.close()
			
			time.sleep(10)
			access_token="f178098933b7b0ba698e0cfc5c8aa40b9a2843b2"
			pullrequest_url = "http://16.16.16.200:3000/api/v1/repos/it_service/Test-IIMS-PLUS/pulls?"
			response= requests.get(f'{pullrequest_url}state=open&sort=oldest&access_token={access_token}')
			resp_list = response.json()
			print(type(resp_list))
			#same_item = (item for item in resp_list if item['title']==jubsu_no)
			for prlist in resp_list:
				print(prlist['title'])
				if jubsu_no==prlist['title']:
					mergeable = prlist['mergeable']
					if not mergeable:
						content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청에 충돌이 있습니다. \n             다시 요청 하시기 바랍니다."""
						dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
						URL = 'http://10.16.16.160/api/giteaApi/webhook'
						response = requests.post(URL, json=dataInfo)
						return
				else:
					continue

			content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정상 접수 되었습니다."""
			dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
			URL = 'http://10.16.16.160/api/giteaApi/webhook'
			response = requests.post(URL, json=dataInfo)

			merge_token="01e4550059f5b717d2eea0a47bdf1ca35ff3a78c"
			params = {
				"access_token": merge_token
			}
			dataInfo = {'Do':'squash','MergeTitleField':jubsu_no,'MergeMessageField':pr_msg}
			merge_url = f"http://16.16.16.200:3000/api/v1/repos/it_service/Test-IIMS-PLUS/pulls/{pr_index}/merge"
			print(merge_url)
			print(dataInfo)
			response= requests.post(merge_url, params = params, json=dataInfo)
			if response.status_code == 200:
				print("PR merge successful.")
				content = f"""□  테스트 IIMS PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 성공했습니다. \n             커밋 목록을 확인하시기 바랍니다."""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return
			else:
				print(f"Failed to merge PR. Status Code: {response.status_code}")
				print(f"Response: {response.text}")
				content = f"""□  테스트 IIMS PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 실패했습니다. \n             에러메시지를 확인해주세요.\n{response.text}"""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/20a53730/MaHSX4CwEq86fS5bCuqsb2Up','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return

			return
			#{'errors': None, 'message': "The target couldn't be found.", 'url': 'http://16.16.16.200:3000/api/swagger'}
			#{'message': '[Do]: Required', 'url': 'http://16.16.16.200:3000/api/swagger'}
	return

@router.post("/prMergeSusuryo")
def pullRequestMergeSusuryo(payload: dict):
	# 1 : 요청등록
	# 2 : 접수
	# 3 : 접수확정
	# 12: 개발접수
	# 4 : 개발승인
	# 5 : 진행
	# 9 : 테스트
	# 13: 테스트완료
	# 6 : 인수승인
	# 10: 이행승인
	# 11: 이행완료
	# 7 : 완료
	# 99: 반려
	repository_dict = {'test_iims_plus','□  PR 요청  □\n'}
	print(payload)
	
	jubsu_no =""
	login_user = ""
	pr_index = ""
	pr_msg = ""
	pr_url = ""
	if payload.get('action') and payload.get('pull_request'):
		value = payload['action']
		if 'opened' in value:
			if type(payload['pull_request']) is dict:
				pr_dict = payload['pull_request']
				print(pr_dict)
				if pr_dict.get("title") and pr_dict.get("user"):
					jubsu_no = pr_dict['title']
					pr_index = pr_dict['number']
					pr_msg = pr_dict['body']
					pr_url = pr_dict['url']
					#print(jubsu_no)
					if type(pr_dict['user']) is dict:
						user_dict = pr_dict['user']
						if user_dict.get("login"):
							#login_user = user_dict['login']
							login_user = user_dict['full_name']

			#print(jubsu_no)
			if not jubsu_no.isdigit() or len(jubsu_no)!=11:
				content = f"""□  수수료 배치 PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청제목은 접수번호만 가능합니다. \n             다시 요청 하시기 바랍니다."""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return

			db = DbLink()

			try:
				#jubsu_no =0
				qry = """select count(*) cnt from info_request where jubsu_no = :jubsu_no and use_yb ='1'
			"""
				bind_arr = {"jubsu_no":jubsu_no}
				db.execute(qry , bind_arr)
				fields = db.get_field_names()
				datas = db.get_datas()
				total_records = ''.join(map(str,datas[0]))
				print(type(total_records))
				total_rec = int(total_records)
				if total_rec==0:
					content = f"""□  수수료 배치 PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정보처리요청게시판에서 조회 할 수 없는 접수번호입니다. \n             다시 요청 하시기 바랍니다."""
					dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
					URL = 'http://10.16.16.160/api/giteaApi/webhook'
					response = requests.post(URL, json=dataInfo)
					db.close()
					return
				else:
					qry = """select count(*) cnt from info_request where jubsu_no = :jubsu_no and use_yb ='1' and status_cd in ('1','2','3','12','4','5','9')
			"""
				bind_arr = {"jubsu_no":jubsu_no}
				db.execute(qry , bind_arr)
				fields = db.get_field_names()
				datas = db.get_datas()
				req_exist = ''.join(map(str,datas[0]))
				#print(type(req_exist))
				req_exist_int = int(req_exist)
				if req_exist_int==0:
					content = f"""□  수수료 배치 PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정보처리요청게시판의 상태가 테스트완료 이후는 더이상 요청 할 수 없습니다. \n             새로운 접수번호로 요청 하시기 바랍니다."""
					dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
					URL = 'http://10.16.16.160/api/giteaApi/webhook'
					response = requests.post(URL, json=dataInfo)
					db.close()
					return
			except Exception as e:
				print("예외발생",e)
				content = f"""□  수수료 배치 PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 예외발생{e}"""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				#dataInfo = {'content':e,'jubsu_no':jubsu_no,'login_user':login_user,'status':'pr'}
				#URL = 'http://air.incar.co.kr/Support/Test/Test3'
				#response = requests.post(URL, data=dataInfo)
				db.close()
				return
			
			time.sleep(10)
			access_token="f178098933b7b0ba698e0cfc5c8aa40b9a2843b2"
			pullrequest_url = "http://16.16.16.200:3000/api/v1/repos/it_service/SusuryoBatch/pulls?"
			response= requests.get(f'{pullrequest_url}state=open&sort=oldest&access_token={access_token}')
			resp_list = response.json()
			print(type(resp_list))
			#same_item = (item for item in resp_list if item['title']==jubsu_no)
			for prlist in resp_list:
				print(prlist['title'])
				if jubsu_no==prlist['title']:
					mergeable = prlist['mergeable']
					if not mergeable:
						content = f"""□  수수료 배치 PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청에 충돌이 있습니다. \n             다시 요청 하시기 바랍니다."""
						dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
						URL = 'http://10.16.16.160/api/giteaApi/webhook'
						response = requests.post(URL, json=dataInfo)
						db.close()
						return
				else:
					continue

			content = f"""□  수수료 배치 PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정상 접수 되었습니다."""
			dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			URL = 'http://10.16.16.160/api/giteaApi/webhook'
			response = requests.post(URL, json=dataInfo)

			merge_token="01e4550059f5b717d2eea0a47bdf1ca35ff3a78c"
			params = {
				"access_token": merge_token
			}
			dataInfo = {'Do':'squash','MergeTitleField':jubsu_no,'MergeMessageField':pr_msg}
			merge_url = f"http://16.16.16.200:3000/api/v1/repos/it_service/TestSusuryoBatch/pulls/{pr_index}/merge"
			print("jubsu_no::",jubsu_no)
			print("pr_msg::",pr_msg)
			print(merge_url)
			print(dataInfo)
			response= requests.post(merge_url, params = params, json=dataInfo)
			print(f"Response: {response.json}")
			if response.status_code == 200:
				print("PR merge successful.")
				access_token="f178098933b7b0ba698e0cfc5c8aa40b9a2843b2"
				commitinfo_url = "http://16.16.16.200:3000/api/v1/repos/it_service/TestSusuryoBatch/commits?'"
				response= requests.get(f'{commitinfo_url}limit=1&access_token={access_token}')
				resp_commitinfo = response.json()
				print("resp_commitinfo",resp_commitinfo)
				commit_hash = resp_commitinfo[0]['sha'][0:7]
				if commit_hash !="":
					print("commit_hash::",commit_hash)
					qry = """select pk from info_request where jubsu_no =:jubsu_no"""
					bind_arr = {"jubsu_no":jubsu_no}
					db.execute(qry , bind_arr)
					fields = db.get_field_names()
					datas = db.get_datas()
					req_pk = ''.join(map(str,datas[0]))
					print("req_pk::",req_pk)
					qry = """insert into git_inforequest_link 
                        (info_request_pk, hash_code, gubun, create_date,upmu_gubun)
                        values
                        (:info_request_pk, :hash_code, '1', sysdate,'3')"""
					bind_arr = {"info_request_pk":req_pk,"hash_code":commit_hash}
					db.execute(qry , bind_arr)
					db.commit()

				content = f"""□  수수료 배치 PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 성공했습니다. \n             커밋 목록을 확인하시기 바랍니다."""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				db.close()
				return
			else:
				print(f"Failed to merge PR. Status Code: {response.status_code}")
				print(f"Response: {response.text}")
				content = f"""□  수수료 배치 PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 실패했습니다. \n             에러메시지를 확인해주세요.\n{response.text}"""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				db.close()
				return
			

			return
			#{'errors': None, 'message': "The target couldn't be found.", 'url': 'http://16.16.16.200:3000/api/swagger'}
			#{'message': '[Do]: Required', 'url': 'http://16.16.16.200:3000/api/swagger'}

@router.post("/fastapiPr")
def pullrequestMerge(payload: dict):
	repository_dict = {'test_iims_plus','□  PR 요청  □\n'}
	print(payload)
	
	jubsu_no =""
	login_user = ""
	pr_index = ""
	pr_msg = ""
	pr_url = ""
	if payload.get('action') and payload.get('pull_request'):
		value = payload['action']
		if 'opened' in value:
			if type(payload['pull_request']) is dict:
				pr_dict = payload['pull_request']
				print(pr_dict)
				if pr_dict.get("title") and pr_dict.get("user"):
					jubsu_no = pr_dict['title']
					pr_index = pr_dict['number']
					pr_msg = pr_dict['body']
					pr_url = pr_dict['url']
					#print(jubsu_no)
					if type(pr_dict['user']) is dict:
						user_dict = pr_dict['user']
						if user_dict.get("login"):
							#login_user = user_dict['login']
							login_user = user_dict['full_name']

			
			time.sleep(10)
			access_token="f178098933b7b0ba698e0cfc5c8aa40b9a2843b2"
			pullrequest_url = "http://16.16.16.200:3000/api/v1/repos/it_service/FastAPI/pulls?"
			response= requests.get(f'{pullrequest_url}state=open&sort=oldest&access_token={access_token}')
			resp_list = response.json()
			print(type(resp_list))
			#same_item = (item for item in resp_list if item['title']==jubsu_no)
			for prlist in resp_list:
				print(prlist['title'])
				if jubsu_no==prlist['title']:
					mergeable = prlist['mergeable']
					if not mergeable:
						content = f"""□  테스트 FastAPI PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청에 충돌이 있습니다. \n             다시 요청 하시기 바랍니다."""
						dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
						URL = 'http://10.16.16.160/api/giteaApi/webhook'
						response = requests.post(URL, json=dataInfo)
						return
				else:
					continue

			content = f"""□  테스트 IIMS PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정상 접수 되었습니다."""
			dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			URL = 'http://10.16.16.160/api/giteaApi/webhook'
			response = requests.post(URL, json=dataInfo)

			merge_token="01e4550059f5b717d2eea0a47bdf1ca35ff3a78c"
			params = {
				"access_token": merge_token
			}
			dataInfo = {'Do':'squash','MergeTitleField':jubsu_no,'MergeMessageField':pr_msg}
			merge_url = f"http://16.16.16.200:3000/api/v1/repos/it_service/FastAPI/pulls/{pr_index}/merge"
			print(merge_url)
			print(dataInfo)
			response= requests.post(merge_url, params = params, json=dataInfo)
			if response.status_code == 200:
				print("PR merge successful.")
				content = f"""□  테스트 IIMS PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 성공했습니다. \n             커밋 목록을 확인하시기 바랍니다."""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return
			else:
				print(f"Failed to merge PR. Status Code: {response.status_code}")
				print(f"Response: {response.text}")
				content = f"""□  테스트 IIMS PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 실패했습니다. \n             에러메시지를 확인해주세요.\n{response.text}"""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return

			return
			#{'errors': None, 'message': "The target couldn't be found.", 'url': 'http://16.16.16.200:3000/api/swagger'}
			#{'message': '[Do]: Required', 'url': 'http://16.16.16.200:3000/api/swagger'}
	return


@router.post("/prMergeAir")
def pullrequestAir(payload: dict):
	jubsu_no =""
	login_user = ""
	pr_index = ""
	pr_msg = ""
	pr_url = ""
	if payload.get('action') and payload.get('pull_request'):
		value = payload['action']
		if 'opened' in value:
			if type(payload['pull_request']) is dict:
				pr_dict = payload['pull_request']
				print(pr_dict)
				if pr_dict.get("title") and pr_dict.get("user"):
					jubsu_no = pr_dict['title']
					pr_index = pr_dict['number']
					pr_msg = pr_dict['body']
					pr_url = pr_dict['url']
					#print(jubsu_no)
					if type(pr_dict['user']) is dict:
						user_dict = pr_dict['user']
						if user_dict.get("login"):
							#login_user = user_dict['login']
							login_user = user_dict['full_name']

			# if not jubsu_no.isdigit() or len(jubsu_no)!=11:
			# 	content = f"""□  테스트 IIMS SERVER PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청제목은 접수번호만 가능합니다. \n             다시 요청 하시기 바랍니다."""
			# 	dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			# 	URL = 'http://10.16.16.160/api/giteaApi/webhook'
			# 	response = requests.post(URL, json=dataInfo)
			# 	return

			# db = DbLink()

			# try:
			# 	#jubsu_no =0
			# 	qry = """select count(*) cnt from info_request where jubsu_no = :jubsu_no and use_yb ='1'
			# """
			# 	bind_arr = {"jubsu_no":jubsu_no}
			# 	db.execute(qry , bind_arr)
			# 	fields = db.get_field_names()
			# 	datas = db.get_datas()
			# 	total_records = ''.join(map(str,datas[0]))
			# 	print(type(total_records))
			# 	total_rec = int(total_records)
			# 	if total_rec==0:
			# 		content = f"""□  테스트 IIMS SERVER PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정보처리요청게시판에서 조회 할 수 없는 접수번호입니다. \n             다시 요청 하시기 바랍니다."""
			# 		dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			# 		URL = 'http://10.16.16.160/api/giteaApi/webhook'
			# 		response = requests.post(URL, json=dataInfo)
			# 		db.close()
			# 		return
			# 	else:
			# 		qry = """select count(*) cnt from info_request where jubsu_no = :jubsu_no and use_yb ='1' and status_cd in ('1','2','3','12','4','5','9')
			# """
			# 	bind_arr = {"jubsu_no":jubsu_no}
			# 	db.execute(qry , bind_arr)
			# 	fields = db.get_field_names()
			# 	datas = db.get_datas()
			# 	req_exist = ''.join(map(str,datas[0]))
			# 	#print(type(req_exist))
			# 	req_exist_int = int(req_exist)
			# 	if req_exist_int==0:
			# 		content = f"""□  테스트 IIMS SERVER PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정보처리요청게시판의 상태가 테스트완료 이후는 더이상 요청 할 수 없습니다. \n             새로운 접수번호로 요청 하시기 바랍니다."""
			# 		dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			# 		URL = 'http://10.16.16.160/api/giteaApi/webhook'
			# 		response = requests.post(URL, json=dataInfo)
			# 		db.close()
			# 		return
			# except Exception as e:
			# 	print("예외발생",e)
			# 	content = f"""□  테스트 IIMS SERVER PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 예외발생{e}"""
			# 	dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			# 	URL = 'http://10.16.16.160/api/giteaApi/webhook'
			# 	response = requests.post(URL, json=dataInfo)
			# 	#dataInfo = {'content':e,'jubsu_no':jubsu_no,'login_user':login_user,'status':'pr'}
			# 	#URL = 'http://air.incar.co.kr/Support/Test/Test3'
			# 	#response = requests.post(URL, data=dataInfo)
			# 	db.close()
			# 	return
			# db.close()
			
			time.sleep(10)
			access_token="f178098933b7b0ba698e0cfc5c8aa40b9a2843b2"
			pullrequest_url = "http://16.16.16.200:3000/api/v1/repos/it_service/Test-IIMS-AIR/pulls?"
			response= requests.get(f'{pullrequest_url}state=open&sort=oldest&access_token={access_token}')
			resp_list = response.json()
			print(type(resp_list))
			#same_item = (item for item in resp_list if item['title']==jubsu_no)
			for prlist in resp_list:
				print(prlist['title'])
				if jubsu_no==prlist['title']:
					mergeable = prlist['mergeable']
					if not mergeable:
						content = f"""□  테스트 IIMS SERVER PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : PR요청에 충돌이 있습니다. \n             다시 요청 하시기 바랍니다."""
						dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
						URL = 'http://10.16.16.160/api/giteaApi/webhook'
						response = requests.post(URL, json=dataInfo)
						return
				else:
					continue

			content = f"""□  테스트 IIMS SERVER PR 요청  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 정상 접수 되었습니다."""
			dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
			URL = 'http://10.16.16.160/api/giteaApi/webhook'
			response = requests.post(URL, json=dataInfo)

			merge_token="01e4550059f5b717d2eea0a47bdf1ca35ff3a78c"
			params = {
				"access_token": merge_token
			}
			dataInfo = {'Do':'squash','MergeTitleField':jubsu_no,'MergeMessageField':pr_msg}
			merge_url = f"http://16.16.16.200:3000/api/v1/repos/it_service/Test-IIMS-AIR/pulls/{pr_index}/merge"
			print(merge_url)
			print(dataInfo)
			response= requests.post(merge_url, params = params, json=dataInfo)
			if response.status_code == 200:
				print("PR merge successful.")
				content = f"""□  테스트 IIMS SERVER PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 성공했습니다. \n             커밋 목록을 확인하시기 바랍니다."""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return
			else:
				print(f"Failed to merge PR. Status Code: {response.status_code}")
				print(f"Response: {response.text}")
				content = f"""□  테스트 IIMS SERVER PR 병합  □\n접수번호 : {jubsu_no}\n작성자 : {login_user}\n처리내용 : 요청 PR의 병합에 실패했습니다. \n             에러메시지를 확인해주세요.\n{response.text}"""
				dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
				URL = 'http://10.16.16.160/api/giteaApi/webhook'
				response = requests.post(URL, json=dataInfo)
				return

			return
			#{'errors': None, 'message': "The target couldn't be found.", 'url': 'http://16.16.16.200:3000/api/swagger'}
			#{'message': '[Do]: Required', 'url': 'http://16.16.16.200:3000/api/swagger'}
	return
