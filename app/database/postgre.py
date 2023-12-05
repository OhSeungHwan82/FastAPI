import psycopg2 as db
import configparser
import os
import platform
class PostgreLink:
	def __init__(self):
		current_branch='' 
		server_ip=''
		if platform.system() == "Windows":
			current_branch = os.popen('git symbolic-ref --short HEAD').read().strip()
		else:
			server_ip = os.popen('hostname -I').read().strip()
		print("server_ip",server_ip)
		if current_branch=='main' or server_ip.startswith("10.16.16.160"):
			config_file = 'prodinfo.ini'
		else:
			config_file = 'testinfo.ini'
		current_directory = os.path.dirname(os.path.abspath(__file__))
		ini_file_path = os.path.join(current_directory, '../config', config_file)
		config = configparser.ConfigParser()
		config.read(ini_file_path)
		user = config['Postgre']['user']
		passwd = config['Postgre']['passwd']
		host = config['Postgre']['host']
		dbname = config['Postgre']['dbname']
		#conn_string="dbname='incar_db' host='16.16.16.200' user='newincar' password='newstart!@3'"
		conn_string=f"dbname='{dbname}' host='{host}' user='{user}' password='{passwd}'"
		self.conn=db.connect(conn_string)
		self.cursor = self.conn.cursor()

	def execute(self, sql: str):
		self.cursor.execute(sql)

	def execute_bind(self, sql: str, arr: dict):
		self.cursor.execute(sql, arr)

	def get_field_names(self):
		return [col[0] for col in self.cursor.description]

	def get_datas(self):
		return self.cursor.fetchall()

	def commit(self):
		self.conn.commit()

	def rollback(self):
		self.conn.rollback()

	def close(self):
		self.cursor.close()
