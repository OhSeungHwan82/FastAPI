import cx_Oracle
import configparser
import os
import platform
class DbLink:
    
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
        else :
            config_file = 'testinfo.ini'
        print("config_file",config_file)
        current_directory = os.path.dirname(os.path.abspath(__file__))
        ini_file_path = os.path.join(current_directory, '../config', config_file)
        config = configparser.ConfigParser()
        config.read(ini_file_path)
        self.user = config['Orcl']['user']
        self.passwd = config['Orcl']['passwd']
        self.host = config['Orcl']['host']
        #self.host_info = f'20.20.20.201:1521/PDB_ONE.INCAR.CO.KR'
        #16.16.16.182:1521/DBLINK.INCAR.CO.KR
        #self.connection = cx_Oracle.connect('NEWINCAR', 'NEWSTART', self.host_info)
        self.connection = cx_Oracle.connect(self.user, self.passwd, self.host)
        self.cursor = self.connection.cursor()

    def execute(self, sql: str):
        self.cursor.execute(sql)

    def execute(self, sql: str, arr: dict):
        self.cursor.execute(sql, arr)

    def get_field_names(self):
        return [col[0] for col in self.cursor.description]

    def get_datas(self):
        return self.cursor.fetchall()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.cursor.close()
        self.connection.close()
